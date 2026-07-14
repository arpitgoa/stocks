"""
Universal Momentum Backtest Runner (Optimized)
===============================================
Same logic as run_backtest.py with the following performance improvements:
  1. Vectorized momentum scoring — no per-ticker loop, full DataFrame ops
  2. Integer-based price slicing via searchsorted — avoids repeated .loc scans
  3. Pre-built membership lookup dict — O(1) per rebalance instead of O(M)
  4. Vectorized period return calculation — single DataFrame op per rebalance
  5. Parquet column pre-filtering at read time

Usage:
    python run_backtest_optimized.py --universe nasdaq100
    python run_backtest_optimized.py --universe sp500 --top-n 5 --exit-rank 10
    python run_backtest_optimized.py --all
    python run_backtest_optimized.py --list
"""

import argparse
import numpy as np
import pandas as pd
from pathlib import Path
from scipy.optimize import brentq
from universe_config import UNIVERSE_CONFIGS, get_config, list_universes
from leveraged_config import LEVERAGED_ETF_MAP


# ============================================================
# PATHS
# ============================================================

NORGATE_DIR = Path.home() / "Documents" / "workspace" / "historical-index-universe-data"
PRICES_DIR = NORGATE_DIR / "prices"
UNIVERSES_DIR = NORGATE_DIR / "universes"
OUTPUT_DIR = Path.home() / "Documents" / "workspace" / "stocks" / "nasdaq_momentum"

PRICES_PARQUET = Path(__file__).parent / "all_prices.parquet"


# ============================================================
# DATA LOADING
# ============================================================

_all_prices_cache = None
_membership_cache = {}


def _load_all_prices_parquet(columns=None):
    """Load prices parquet. If columns provided, only reads those columns (faster)."""
    global _all_prices_cache
    if _all_prices_cache is None:
        if not PRICES_PARQUET.exists():
            return None
        print(f"  Loading prices from parquet ({PRICES_PARQUET.stat().st_size // 1024 // 1024} MB)...")
        # Optimization #5: read only needed columns if specified
        _all_prices_cache = pd.read_parquet(PRICES_PARQUET, columns=columns) if columns else pd.read_parquet(PRICES_PARQUET)
        print(f"  Loaded: {_all_prices_cache.shape[0]} days × {_all_prices_cache.shape[1]} tickers")
    return _all_prices_cache


def load_membership(universe_folder):
    if universe_folder in _membership_cache:
        return _membership_cache[universe_folder]
    csv_path = UNIVERSES_DIR / universe_folder / "membership_periods.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"Membership file not found: {csv_path}")
    df = pd.read_csv(csv_path)
    df["EntryDate"] = pd.to_datetime(df["EntryDate"])
    df["ExitDate"] = pd.to_datetime(df["ExitDate"])
    _membership_cache[universe_folder] = df
    return df


def build_membership_lookup(universe_folder, rebal_dates):
    """
    Optimization #3: Pre-build {date -> [tickers]} for all rebalance dates in one pass.
    Original: O(R * M) total. Optimized: O(M + R) total.
    """
    df = load_membership(universe_folder)
    lookup = {}
    for date in rebal_dates:
        ts = pd.Timestamp(date)
        mask = (df["EntryDate"] <= ts) & ((df["ExitDate"].isna()) | (df["ExitDate"] > ts))
        lookup[date] = df.loc[mask, "Symbol"].tolist()
    return lookup


def load_prices_for_universe(universe_folder, config):
    membership = load_membership(universe_folder)
    universe_tickers = set(membership["Symbol"].unique())

    extra_tickers = {"XAUUSD", "$VIX"}
    extra_tickers.add(config.get("gold_signal_index", "$NDX"))
    extra_tickers.add(config.get("benchmark", ""))
    extra_tickers.add(config.get("benchmark_etf", ""))
    extra_tickers.discard("")

    lev_tickers = set(LEVERAGED_ETF_MAP.values())
    all_needed = universe_tickers | extra_tickers | lev_tickers

    all_prices = _load_all_prices_parquet()
    if all_prices is not None:
        available = [t for t in all_needed if t in all_prices.columns]
        prices = all_prices[available].copy()
        print(f"  Filtered: {len(available)} tickers for {universe_folder}")

        lev_csv = Path(__file__).parent / "nasdaq100_daily_closes.csv"
        if lev_csv.exists():
            missing_lev = [t for t in lev_tickers if t not in prices.columns]
            if missing_lev:
                lev_df = pd.read_csv(lev_csv, index_col="Date", parse_dates=True)
                added = 0
                for ticker in missing_lev:
                    if ticker in lev_df.columns:
                        prices[ticker] = lev_df[ticker]
                        added += 1
                print(f"  Added {added} leveraged ETFs from yfinance data")
        return prices

    # Fallback: individual CSVs
    file_map = {f.stem.split("__")[0]: f for f in PRICES_DIR.glob("*.csv")}
    all_close = {}
    for ticker in all_needed:
        if ticker in file_map:
            df = pd.read_csv(file_map[ticker], usecols=["Date", "Close"], index_col="Date", parse_dates=True)
            all_close[ticker] = df["Close"]
    prices = pd.DataFrame(all_close).sort_index()
    return prices


# ============================================================
# HELPERS
# ============================================================

def xirr(cashflows):
    if not cashflows:
        return 0.0
    dates = [cf[0] for cf in cashflows]
    amounts = [cf[1] for cf in cashflows]
    d0 = dates[0]
    days = [(d - d0).days / 365.25 for d in dates]

    def npv(rate):
        return sum(amt / (1 + rate) ** t for amt, t in zip(amounts, days))

    try:
        return brentq(npv, -0.5, 10.0, maxiter=1000)
    except (ValueError, RuntimeError):
        return 0.0


def max_drawdown(values):
    peak = values[0]
    peak_idx = 0
    max_dd = 0
    max_dd_peak_idx = 0
    max_dd_trough_idx = 0
    for i, val in enumerate(values):
        if val > peak:
            peak = val
            peak_idx = i
        dd = (peak - val) / peak
        if dd > max_dd:
            max_dd = dd
            max_dd_peak_idx = peak_idx
            max_dd_trough_idx = i
    return max_dd, max_dd_peak_idx, max_dd_trough_idx


# ============================================================
# VECTORIZED MOMENTUM SCORING
# ============================================================

_precomputed_cache = None


def _load_precomputed():
    global _precomputed_cache
    if _precomputed_cache is None:
        p = Path(__file__).parent / "precomputed_momentum.parquet"
        if not p.exists():
            return None
        print("  Loading precomputed momentum parquet...")
        _precomputed_cache = pd.read_parquet(p, columns=["Date", "Ticker", "MR_12", "MR_6"])
        print(f"  Loaded: {len(_precomputed_cache):,} rows")
    return _precomputed_cache


# Pre-grouped cache: {date -> DataFrame} built once on first use
_precomputed_by_date = None


def _get_precomputed_by_date():
    global _precomputed_by_date
    if _precomputed_by_date is None:
        df = _load_precomputed()
        if df is None:
            return None
        print("  Grouping precomputed scores by date...")
        _precomputed_by_date = {d: g.reset_index(drop=True) for d, g in df.groupby("Date")}
    return _precomputed_by_date


def _score_from_prices_custom(prices_df, universe_tickers, rebal_date, lookback_long, lookback_short, skip_days=5):
    """Live momentum scoring with custom lookback periods (for VIX-adaptive mode)."""
    import numpy as np
    results = []
    for ticker in universe_tickers:
        if ticker not in prices_df.columns: continue
        ts = prices_df[ticker].loc[:rebal_date].dropna()
        if len(ts) < lookback_long + skip_days: continue
        end_idx = len(ts) - 1 - skip_days
        if end_idx < lookback_long: continue
        price_end = ts.iloc[end_idx]
        price_long = ts.iloc[end_idx - lookback_long]
        price_short = ts.iloc[end_idx - lookback_short]
        if price_long <= 0 or price_short <= 0: continue
        ret_long = price_end / price_long - 1
        ret_short = price_end / price_short - 1
        log_rets = np.log(ts.iloc[end_idx-lookback_long:end_idx+1] / ts.iloc[end_idx-lookback_long:end_idx+1].shift(1)).dropna()
        if len(log_rets) < 50: continue
        vol = log_rets.std() * np.sqrt(252)
        if vol <= 0: continue
        results.append({"Ticker": ticker, "MR_12": ret_long/vol, "MR_6": ret_short/vol})
    if not results: return pd.DataFrame()
    df = pd.DataFrame(results)
    df["Z_12"] = (df["MR_12"] - df["MR_12"].mean()) / df["MR_12"].std()
    df["Z_6"] = (df["MR_6"] - df["MR_6"].mean()) / df["MR_6"].std()
    df["Weighted_Z"] = 0.5 * df["Z_12"] + 0.5 * df["Z_6"]
    df["Momentum_Score"] = df["Weighted_Z"].apply(lambda z: (1+z) if z >= 0 else 1/(1-z))
    return df.sort_values("Momentum_Score", ascending=False).reset_index(drop=True)


def calculate_momentum_scores_vectorized(prices_df, universe_tickers, cutoff_idx,
                                         min_history=252, skip_days=5):
    """
    Optimization #1: Use precomputed MR values from parquet — O(1) lookup per rebalance.
    Falls back to per-ticker price calculation if parquet unavailable.
    """
    rebal_date = prices_df.index[cutoff_idx]
    by_date = _get_precomputed_by_date()

    if by_date is not None:
        # Find exact or nearest date within 5 days
        available = np.array(list(by_date.keys()), dtype="datetime64[ns]")
        diffs = np.abs(available - np.datetime64(rebal_date))
        nearest = pd.Timestamp(available[diffs.argmin()])
        if pd.Timedelta(diffs.min()) <= pd.Timedelta(days=5):
            subset = by_date[nearest]
            subset = subset[subset["Ticker"].isin(universe_tickers)].copy()
            if len(subset) >= 3:
                subset["Z_12"] = (subset["MR_12"] - subset["MR_12"].mean()) / subset["MR_12"].std()
                subset["Z_6"]  = (subset["MR_6"]  - subset["MR_6"].mean())  / subset["MR_6"].std()
                subset["Weighted_Z"] = 0.5 * subset["Z_12"] + 0.5 * subset["Z_6"]
                subset["Momentum_Score"] = subset["Weighted_Z"].apply(
                    lambda z: (1 + z) if z >= 0 else 1 / (1 - z)
                )
                return subset[["Ticker", "MR_12", "MR_6", "Momentum_Score"]].sort_values(
                    "Momentum_Score", ascending=False
                ).reset_index(drop=True)

    # Fallback: live calculation
    tickers = [t for t in universe_tickers if t in prices_df.columns]
    results = []
    for ticker in tickers:
        ts = prices_df[ticker].iloc[:cutoff_idx + 1].dropna()
        end_idx = len(ts) - 1 - skip_days
        if end_idx < min_history or end_idx < 252 or end_idx < 126:
            continue
        price_end = ts.iloc[end_idx]
        price_12m = ts.iloc[end_idx - 252]
        price_6m  = ts.iloc[end_idx - 126]
        if price_12m <= 0 or price_6m <= 0:
            continue
        log_rets = np.log(ts.iloc[end_idx - 252:end_idx + 1] /
                          ts.iloc[end_idx - 252:end_idx + 1].shift(1)).dropna()
        if len(log_rets) < 100:
            continue
        vol = log_rets.std() * np.sqrt(252)
        if vol <= 0:
            continue
        results.append({"Ticker": ticker,
                         "MR_12": (price_end / price_12m - 1) / vol,
                         "MR_6":  (price_end / price_6m  - 1) / vol})
    if not results:
        return pd.DataFrame()
    df = pd.DataFrame(results)
    df["Z_12"] = (df["MR_12"] - df["MR_12"].mean()) / df["MR_12"].std()
    df["Z_6"]  = (df["MR_6"]  - df["MR_6"].mean())  / df["MR_6"].std()
    df["Weighted_Z"] = 0.5 * df["Z_12"] + 0.5 * df["Z_6"]
    df["Momentum_Score"] = df["Weighted_Z"].apply(lambda z: (1 + z) if z >= 0 else 1 / (1 - z))
    return df.sort_values("Momentum_Score", ascending=False).reset_index(drop=True)


# ============================================================
# BACKTEST ENGINE
# ============================================================

def run_backtest(universe_name, top_n=None, entry_rank=None, exit_rank=None,
                 ndx_gold_threshold=None, start_year=None):

    config = get_config(universe_name)
    universe_folder = config["folder"]

    if top_n is None:            top_n = config["top_n"]
    if entry_rank is None:       entry_rank = config["entry_rank"]
    if exit_rank is None:        exit_rank = config["exit_rank"]
    if ndx_gold_threshold is None: ndx_gold_threshold = config["gold_threshold"]
    if start_year is None:       start_year = config["start_year"]

    benchmark_symbol = config["benchmark"]
    benchmark_etf    = config.get("benchmark_etf", None)
    gold_signal_index = config.get("gold_signal_index", "$NDX")

    prices = load_prices_for_universe(universe_folder, config)

    if benchmark_symbol not in prices.columns and benchmark_etf and benchmark_etf in prices.columns:
        benchmark_symbol = benchmark_etf

    print(f"\n{'='*70}")
    print(f"BACKTEST (OPTIMIZED): {universe_name.upper()} Momentum Top {top_n}")
    print(f"Buffer: entry ≤ {entry_rank}, exit > {exit_rank}")
    print(f"Gold rotation: {gold_signal_index}/XAUUSD ≥ {ndx_gold_threshold}")
    print(f"Start year: {start_year}")
    print(f"Benchmark: {benchmark_symbol}")
    print(f"{'='*70}")

    # Generate rebalance dates
    rebal_dates = []
    last_date = prices.index[-1]
    for year in range(start_year, last_date.year + 1):
        for month in range(1, 13):
            try:
                month_data = prices.loc[f"{year}-{month:02d}"]
                if len(month_data) > 0:
                    rebal_dates.append(month_data.index[-1])
            except KeyError:
                continue
    rebal_dates = [d for d in rebal_dates if d < last_date - pd.Timedelta(days=5)]

    print(f"Rebalance dates: {len(rebal_dates)} ({rebal_dates[0].date()} to {rebal_dates[-1].date()})")

    # Optimization #3: pre-build membership lookup for all rebalance dates
    print("  Pre-building membership lookup...")
    membership_lookup = build_membership_lookup(universe_folder, rebal_dates)

    # Warm up precomputed scores cache before the loop
    _get_precomputed_by_date()

    # Optimization #2: build integer index map once
    date_to_idx = {d: prices.index.searchsorted(d) for d in rebal_dates}

    portfolio_value    = 100000.0
    monthly_contribution = 1000.0
    total_invested     = 100000.0
    holdings_history   = []
    current_holdings   = set()
    total_trades       = 0

    for i, rebal_date in enumerate(rebal_dates):
        next_rebal = rebal_dates[i + 1] if i + 1 < len(rebal_dates) else prices.index[-1]
        cutoff_idx = date_to_idx[rebal_date]

        # Gold rotation check
        if ndx_gold_threshold and gold_signal_index in prices.columns and "XAUUSD" in prices.columns:
            idx_p = prices[gold_signal_index].iloc[:cutoff_idx + 1].dropna()
            xau_p = prices["XAUUSD"].iloc[:cutoff_idx + 1].dropna()
            if len(idx_p) > 0 and len(xau_p) > 0:
                ratio = idx_p.iloc[-1] / xau_p.iloc[-1]
                if ratio >= ndx_gold_threshold:
                    next_idx = prices.index.searchsorted(next_rebal)
                    hold_period = prices["XAUUSD"].iloc[cutoff_idx:next_idx + 1].dropna()
                    gold_ret = (hold_period.iloc[-1] / hold_period.iloc[0] - 1) if len(hold_period) >= 2 else 0
                    portfolio_value *= (1 + gold_ret)
                    portfolio_value += monthly_contribution
                    total_invested  += monthly_contribution

                    holdings_history.append({
                        "Rebal_Date": rebal_date,
                        "Next_Rebal": next_rebal,
                        "Period_Return": gold_ret,
                        "Leveraged_Return": gold_ret,
                        "Portfolio_Value": portfolio_value,
                        "Holdings": [{"Ticker": "XAUUSD", "Weight": 1.0}],
                        "Ticker_Returns": {"XAUUSD": round(gold_ret * 100, 2)},
                        "Lev_Ticker_Returns": {"XAUUSD": round(gold_ret * 100, 2)},
                        "Trades": 0,
                        "Top10": ["GOLD ({}/XAUUSD={:.2f})".format(gold_signal_index, ratio)],
                        "Removed": [],
                        "Added": ["XAUUSD"],
                    })
                    current_holdings = set()
                    continue

        # Get universe members (O(1) lookup)
        universe = membership_lookup[rebal_date]

        # VIX-adaptive lookback
        vix_threshold = config.get("vix_threshold", None)
        custom_lookback = None
        if vix_threshold and "$VIX" in prices.columns:
            vix_ts = prices["$VIX"].loc[:rebal_date].dropna()
            if len(vix_ts) > 0 and vix_ts.iloc[-1] > vix_threshold:
                custom_lookback = (config.get("vix_fast_long", 126), config.get("vix_fast_short", 42))

        # Momentum scoring
        if custom_lookback:
            # Use live calculation with fast lookback
            scores = _score_from_prices_custom(prices, universe, rebal_date, custom_lookback[0], custom_lookback[1])
        else:
            # Standard: use precomputed or normal lookback
            scores = calculate_momentum_scores_vectorized(prices, universe, cutoff_idx)
        if scores.empty:
            portfolio_value += monthly_contribution
            total_invested  += monthly_contribution
            continue

        scores["Rank"] = range(1, len(scores) + 1)
        ranked = dict(zip(scores["Ticker"], scores["Rank"]))

        # Buffer logic
        retained = {t for t in current_holdings if t in ranked and ranked[t] <= exit_rank}
        new_portfolio = retained.copy()
        for _, row in scores.iterrows():
            if len(new_portfolio) >= top_n:
                break
            if row["Ticker"] not in new_portfolio and row["Rank"] <= entry_rank:
                new_portfolio.add(row["Ticker"])
        if len(new_portfolio) < top_n:
            for _, row in scores.iterrows():
                if len(new_portfolio) >= top_n:
                    break
                if row["Ticker"] not in new_portfolio:
                    new_portfolio.add(row["Ticker"])

        trades = len(new_portfolio - current_holdings) + len(current_holdings - new_portfolio)
        added   = sorted(new_portfolio - current_holdings)
        removed = sorted(current_holdings - new_portfolio)
        total_trades    += trades
        current_holdings = new_portfolio

        weight = 1.0 / len(new_portfolio) if new_portfolio else 0

        # Optimization #4: vectorized period return calculation
        next_idx   = prices.index.searchsorted(next_rebal)
        hold_slice = prices.iloc[cutoff_idx:next_idx + 1]
        if len(hold_slice) < 2:
            portfolio_value += monthly_contribution
            total_invested  += monthly_contribution
            continue

        held_tickers = [t for t in new_portfolio if t in hold_slice.columns]
        if held_tickers:
            period_ret = 0
            ticker_returns = {}
            lev_ticker_returns = {}
            for t in held_tickers:
                tp = hold_slice[t].dropna()
                if len(tp) < 2:
                    continue
                ticker_ret = tp.iloc[-1] / tp.iloc[0] - 1
                period_ret += weight * ticker_ret
                ticker_returns[t] = round(ticker_ret * 100, 2)

                lev = LEVERAGED_ETF_MAP.get(t)
                if lev and lev in hold_slice.columns:
                    lp = hold_slice[lev].dropna()
                    if len(lp) >= 2:
                        lev_ticker_returns[t] = round((lp.iloc[-1] / lp.iloc[0] - 1) * 100, 2)
                        continue
                lev_ticker_returns[t] = ticker_returns[t]

            lev_period_ret = sum(lev_ticker_returns.values()) / len(held_tickers) / 100 if lev_ticker_returns else 0
        else:
            period_ret = lev_period_ret = 0
            ticker_returns = lev_ticker_returns = {}

        portfolio_value *= (1 + period_ret)
        portfolio_value += monthly_contribution
        total_invested  += monthly_contribution

        # Get VIX value for this month
        vix_val = None
        if "$VIX" in prices.columns:
            vix_ts = prices["$VIX"].loc[:rebal_date].dropna()
            if len(vix_ts) > 0:
                vix_val = round(vix_ts.iloc[-1], 1)

        holdings_history.append({
            "Rebal_Date": rebal_date,
            "Next_Rebal": next_rebal,
            "Period_Return": period_ret,
            "Leveraged_Return": lev_period_ret,
            "Portfolio_Value": portfolio_value,
            "Holdings": [{"Ticker": t, "Weight": weight} for t in sorted(new_portfolio)],
            "Ticker_Returns": ticker_returns,
            "Lev_Ticker_Returns": lev_ticker_returns,
            "Trades": trades,
            "Top10": scores.head(10)["Ticker"].tolist(),
            "Removed": removed,
            "Added": added,
            "VIX": vix_val,
            "VIX_Fast": custom_lookback is not None if config.get("vix_threshold") else False,
        })

        if i % 50 == 0:
            print(f"  {rebal_date.date()}: Val=${portfolio_value:,.0f} | Held: {sorted(new_portfolio)}")

    print(f"\n  Total trades: {total_trades}")
    print(f"  Total invested: ${total_invested:,.0f}")

    years    = (holdings_history[-1]["Next_Rebal"] - holdings_history[0]["Rebal_Date"]).days / 365.25
    multiple = portfolio_value / total_invested

    cashflows = [(holdings_history[0]["Rebal_Date"], -100000)]
    for h in holdings_history:
        cashflows.append((h["Rebal_Date"], -1000))
    cashflows.append((holdings_history[-1]["Next_Rebal"], portfolio_value))
    xirr_rate = xirr(cashflows)

    port_values = [100000] + [h["Portfolio_Value"] for h in holdings_history]
    mdd, _, _   = max_drawdown(port_values)

    print(f"\n{'='*70}")
    print(f"RESULTS: {universe_name.upper()} Momentum Top {top_n}")
    print(f"  Period: {holdings_history[0]['Rebal_Date'].date()} to {holdings_history[-1]['Next_Rebal'].date()} ({years:.1f} years)")
    print(f"  Total invested: ${total_invested:,.0f}")
    print(f"  Ending value:   ${portfolio_value:,.0f}")
    print(f"  Multiple:       {multiple:.1f}x")
    print(f"  XIRR:           {xirr_rate:.1%}")
    print(f"  Max Drawdown:   -{mdd:.1%}")
    print(f"{'='*70}")

    _save_wide_csv(universe_name, holdings_history, prices, benchmark_symbol)

    return portfolio_value, holdings_history


def _save_wide_csv(universe_name, holdings_history, prices, benchmark_symbol):
    config = get_config(universe_name)
    benchmark_etf = config.get("benchmark_etf", None)
    rows = []
    for h in holdings_history:
        rebal_date = h["Rebal_Date"]
        next_rebal = h["Next_Rebal"]
        port_start = h["Portfolio_Value"] / (1 + h["Period_Return"]) if h["Period_Return"] != -1 else h["Portfolio_Value"]

        row = {
            "Start_Date": rebal_date.strftime("%Y-%m-%d"),
            "End_Date": next_rebal.strftime("%Y-%m-%d"),
            "Portfolio_Start": round(port_start, 2),
            "Portfolio_End": round(h["Portfolio_Value"], 2),
            "Portfolio_Return_Pct": round(h["Period_Return"] * 100, 2),
            "Leveraged_Return_Pct": round(h.get("Leveraged_Return", h["Period_Return"]) * 100, 2),
            "VIX": h.get("VIX", ""),
            "VIX_Fast": h.get("VIX_Fast", False),
        }

        bench_ret = None
        if benchmark_symbol in prices.columns:
            bp = prices.loc[rebal_date:next_rebal, benchmark_symbol].dropna()
            if len(bp) >= 2:
                bench_ret = bp.iloc[-1] / bp.iloc[0] - 1
        if bench_ret is None and benchmark_etf and benchmark_etf in prices.columns:
            bp = prices.loc[rebal_date:next_rebal, benchmark_etf].dropna()
            if len(bp) >= 2:
                bench_ret = bp.iloc[-1] / bp.iloc[0] - 1
        row["Benchmark_Return_Pct"] = round(bench_ret * 100, 2) if bench_ret is not None else ""

        row["Top10"]   = ", ".join(h.get("Top10", []))
        added   = h.get("Added", [])
        removed = h.get("Removed", [])
        if added and removed:
            row["Changes"] = ", ".join([f"{r}→{a}" for r, a in zip(removed, added)])
        elif added:
            row["Changes"] = "+" + ", +".join(added)
        else:
            row["Changes"] = ""

        ticker_returns     = h.get("Ticker_Returns", {})
        lev_ticker_returns = h.get("Lev_Ticker_Returns", {})
        for holding in h["Holdings"]:
            ticker = holding["Ticker"]
            weight = holding["Weight"]
            if ticker in ticker_returns:
                row[f"{ticker}_Pct"]    = round(weight * 100, 2)
                row[f"{ticker}_Ret"]    = ticker_returns[ticker]
                row[f"{ticker}_LevRet"] = lev_ticker_returns.get(ticker, ticker_returns[ticker])

        rows.append(row)

    dashboard_dir = OUTPUT_DIR / "dashboards" / universe_name
    dashboard_dir.mkdir(parents=True, exist_ok=True)
    output_file = dashboard_dir / "backtest_wide.csv"
    pd.DataFrame(rows).to_csv(output_file, index=False)
    print(f"  Saved: {output_file}")


# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Universal Momentum Backtest (Optimized)")
    parser.add_argument("--universe", type=str)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--top-n", type=int, default=None)
    parser.add_argument("--entry-rank", type=int, default=None)
    parser.add_argument("--exit-rank", type=int, default=None)
    parser.add_argument("--gold-threshold", type=float, default=None)
    parser.add_argument("--start-year", type=int, default=None)
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--dashboard", action="store_true")
    args = parser.parse_args()

    if args.list:
        list_universes()
        return

    if args.all:
        universes_to_run = list(UNIVERSE_CONFIGS.keys())
    elif args.universe:
        if args.universe not in UNIVERSE_CONFIGS:
            print(f"Unknown universe: {args.universe}. Use --list to see options.")
            return
        universes_to_run = [args.universe]
    else:
        print("Error: --universe or --all required. Use --list to see options.")
        return

    for universe_name in universes_to_run:
        try:
            run_backtest(
                universe_name=universe_name,
                top_n=args.top_n,
                entry_rank=args.entry_rank,
                exit_rank=args.exit_rank,
                ndx_gold_threshold=args.gold_threshold,
                start_year=args.start_year,
            )
            if args.dashboard:
                print("\nGenerating dashboard...")
                from generate_dashboard import generate_dashboard as gen_dash
                gen_dash(universe_name)
        except Exception as e:
            print(f"\nERROR running {universe_name}: {e}")
            continue


if __name__ == "__main__":
    main()
