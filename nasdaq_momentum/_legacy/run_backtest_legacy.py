"""
Universal Momentum Backtest Runner
===================================
Runs the Top 3 momentum strategy on any supported universe.

Usage:
    python run_backtest.py --universe nasdaq100
    python run_backtest.py --universe sp500
    python run_backtest.py --universe russell1000
    python run_backtest.py --universe sp500 --top-n 5 --exit-rank 10
    python run_backtest.py --list

Outputs:
    - {universe}_backtest_wide.csv
    - {universe}_momentum_dashboard.html (if --dashboard flag)
"""

import argparse
import os
import sys
import numpy as np
import pandas as pd
from datetime import datetime
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

# Available universes loaded from universe_config.py
UNIVERSES = UNIVERSE_CONFIGS


# ============================================================
# DATA LOADING
# ============================================================

_price_file_map = None
_membership_cache = {}
_all_prices_cache = None

PRICES_PARQUET = Path(__file__).parent / "all_prices.parquet"


def _load_all_prices_parquet():
    """Load the combined prices parquet (cached)."""
    global _all_prices_cache
    if _all_prices_cache is None:
        if PRICES_PARQUET.exists():
            print(f"  Loading prices from parquet ({PRICES_PARQUET.stat().st_size // 1024 // 1024} MB)...")
            _all_prices_cache = pd.read_parquet(PRICES_PARQUET)
            print(f"  Loaded: {_all_prices_cache.shape[0]} days × {_all_prices_cache.shape[1]} tickers")
        else:
            return None
    return _all_prices_cache


def _get_price_file_map():
    """Build a map of symbol -> file path (cached). Fallback if no parquet."""
    global _price_file_map
    if _price_file_map is None:
        _price_file_map = {f.stem.split("__")[0]: f for f in PRICES_DIR.glob("*.csv")}
        print(f"  Price file index: {len(_price_file_map)} files available")
    return _price_file_map


def load_prices_for_universe(universe_folder, config):
    """Load prices for a specific universe. Uses parquet if available, else CSVs."""

    # Try parquet first (fast path)
    all_prices = _load_all_prices_parquet()
    if all_prices is not None:
        # Get tickers needed for this universe
        membership = load_membership(universe_folder)
        universe_tickers = set(membership["Symbol"].unique())

        extra_tickers = {"XAUUSD"}
        extra_tickers.add(config.get("gold_signal_index", "$NDX"))
        extra_tickers.add(config.get("benchmark", ""))
        extra_tickers.add(config.get("benchmark_etf", ""))
        extra_tickers.discard("")

        # Add leveraged ETF tickers
        lev_tickers = set(LEVERAGED_ETF_MAP.values())

        all_needed = universe_tickers | extra_tickers | lev_tickers
        # Filter to columns that exist
        available = [t for t in all_needed if t in all_prices.columns]
        prices = all_prices[available].copy()
        print(f"  Filtered: {len(available)} tickers for {universe_folder}")

        # Load leveraged ETF prices from yfinance CSV if not in parquet
        lev_csv = Path(__file__).parent / "nasdaq100_daily_closes.csv"
        if lev_csv.exists():
            missing_lev = [t for t in lev_tickers if t not in prices.columns]
            if missing_lev:
                lev_df = pd.read_csv(lev_csv, index_col="Date", parse_dates=True)
                for ticker in missing_lev:
                    if ticker in lev_df.columns:
                        prices[ticker] = lev_df[ticker]
                print(f"  Added {sum(1 for t in missing_lev if t in prices.columns)} leveraged ETFs from yfinance data")

        return prices

    # Fallback: read individual CSVs
    file_map = _get_price_file_map()
    membership = load_membership(universe_folder)
    universe_tickers = set(membership["Symbol"].unique())

    extra_tickers = {"XAUUSD"}
    extra_tickers.add(config.get("gold_signal_index", "$NDX"))
    extra_tickers.add(config.get("benchmark", ""))
    extra_tickers.add(config.get("benchmark_etf", ""))
    extra_tickers.discard("")

    all_tickers = universe_tickers | extra_tickers

    print(f"  Loading prices for {len(all_tickers)} tickers from CSVs...")
    all_close = {}
    for ticker in all_tickers:
        if ticker in file_map:
            df = pd.read_csv(file_map[ticker], usecols=["Date", "Close"], index_col="Date", parse_dates=True)
            all_close[ticker] = df["Close"]

    prices = pd.DataFrame(all_close).sort_index()
    print(f"  Loaded: {len(all_close)} tickers, {prices.shape[0]} days")
    return prices


def load_membership(universe_folder):
    """Load SCD2 membership for a universe."""
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


def get_members_at_date(universe_folder, date_str):
    """Get active members of a universe on a given date."""
    df = load_membership(universe_folder)

    if isinstance(date_str, str):
        check_date = pd.Timestamp(date_str)
    else:
        check_date = pd.Timestamp(date_str)

    active = df[
        (df["EntryDate"] <= check_date) &
        ((df["ExitDate"].isna()) | (df["ExitDate"] > check_date))
    ]
    return active["Symbol"].tolist()


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def xirr(cashflows):
    """Calculate XIRR given a list of (date, amount) tuples."""
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
    """Calculate maximum drawdown from a series of portfolio values."""
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
# MOMENTUM SCORE CALCULATION
# ============================================================
# MOMENTUM SCORING (precomputed parquet)
# ============================================================

PARQUET_FILE = Path(__file__).parent / "precomputed_momentum.parquet"
_scores_cache = None


def _load_precomputed_scores():
    """Load the precomputed momentum parquet (cached)."""
    global _scores_cache
    if _scores_cache is None:
        if not PARQUET_FILE.exists():
            return None
        print(f"  Loading precomputed scores from parquet...")
        _scores_cache = pd.read_parquet(PARQUET_FILE)
        print(f"  Loaded: {len(_scores_cache):,} rows")
    return _scores_cache


def calculate_momentum_scores(prices_df, universe_tickers, rebal_date,
                              min_history=252, skip_days=5):
    """
    Calculate Normalized Momentum Score for all eligible tickers.
    Uses live calculation from price data (guaranteed accurate).
    """
    return _score_from_prices(prices_df, universe_tickers, rebal_date, min_history, skip_days)


def _score_from_precomputed(scores_df, universe_tickers, rebal_date):
    """Score stocks using precomputed MR values + Z-scoring per universe."""
    rebal_ts = pd.Timestamp(rebal_date)

    # Find closest date in precomputed data
    available_dates = scores_df["Date"].unique()
    # Find exact or nearest date
    exact = scores_df[scores_df["Date"] == rebal_ts]
    if exact.empty:
        # Find nearest date within 5 days
        diffs = abs(pd.to_datetime(available_dates) - rebal_ts)
        nearest_idx = diffs.argmin()
        if diffs[nearest_idx].days > 5:
            return pd.DataFrame()
        rebal_ts = pd.Timestamp(available_dates[nearest_idx])
        exact = scores_df[scores_df["Date"] == rebal_ts]

    # Filter to universe members
    universe = exact[exact["Ticker"].isin(universe_tickers)].copy()
    if len(universe) < 3:
        return pd.DataFrame()

    # Z-score within universe (same logic as live)
    universe["Z_12"] = (universe["MR_12"] - universe["MR_12"].mean()) / universe["MR_12"].std()
    universe["Z_6"] = (universe["MR_6"] - universe["MR_6"].mean()) / universe["MR_6"].std()
    universe["Weighted_Z"] = 0.5 * universe["Z_12"] + 0.5 * universe["Z_6"]
    universe["Momentum_Score"] = universe["Weighted_Z"].apply(
        lambda z: (1 + z) if z >= 0 else 1 / (1 - z)
    )

    universe = universe.sort_values("Momentum_Score", ascending=False).reset_index(drop=True)
    return universe[["Ticker", "MR_12", "MR_6", "Momentum_Score"]]


def _score_from_prices(prices_df, universe_tickers, rebal_date,
                       min_history=252, skip_days=5):
    """Fallback: Calculate momentum scores from raw price data."""
    results = []

    for ticker in universe_tickers:
        if ticker not in prices_df.columns:
            continue

        ts = prices_df[ticker].loc[:rebal_date].dropna()
        if len(ts) < min_history + skip_days:
            continue

        end_idx = len(ts) - 1 - skip_days
        if end_idx < min_history:
            continue

        price_end = ts.iloc[end_idx]
        price_12m = ts.iloc[end_idx - 252] if end_idx >= 252 else None
        price_6m = ts.iloc[end_idx - 126] if end_idx >= 126 else None

        if price_12m is None or price_6m is None:
            continue
        if price_12m <= 0 or price_6m <= 0:
            continue

        ret_12m = price_end / price_12m - 1
        ret_6m = price_end / price_6m - 1

        log_rets = np.log(
            ts.iloc[end_idx - 252:end_idx + 1] /
            ts.iloc[end_idx - 252:end_idx + 1].shift(1)
        ).dropna()

        if len(log_rets) < 100:
            continue

        vol = log_rets.std() * np.sqrt(252)
        if vol <= 0:
            continue

        mr_12 = ret_12m / vol
        mr_6 = ret_6m / vol

        results.append({
            "Ticker": ticker,
            "MR_12": mr_12,
            "MR_6": mr_6,
        })

    if not results:
        return pd.DataFrame()

    df = pd.DataFrame(results)
    df["Z_12"] = (df["MR_12"] - df["MR_12"].mean()) / df["MR_12"].std()
    df["Z_6"] = (df["MR_6"] - df["MR_6"].mean()) / df["MR_6"].std()
    df["Weighted_Z"] = 0.5 * df["Z_12"] + 0.5 * df["Z_6"]
    df["Momentum_Score"] = df["Weighted_Z"].apply(
        lambda z: (1 + z) if z >= 0 else 1 / (1 - z)
    )
    df = df.sort_values("Momentum_Score", ascending=False).reset_index(drop=True)
    return df


# ============================================================
# BACKTEST ENGINE
# ============================================================

def run_backtest(universe_name, top_n=None, entry_rank=None, exit_rank=None,
                 ndx_gold_threshold=None, start_year=None):
    """Run the full momentum backtest on a given universe."""

    config = get_config(universe_name)
    universe_folder = config["folder"]

    # Use config values as defaults, allow CLI overrides
    if top_n is None:
        top_n = config["top_n"]
    if entry_rank is None:
        entry_rank = config["entry_rank"]
    if exit_rank is None:
        exit_rank = config["exit_rank"]
    if ndx_gold_threshold is None:
        ndx_gold_threshold = config["gold_threshold"]
    if start_year is None:
        start_year = config["start_year"]
    benchmark_symbol = config["benchmark"]
    benchmark_etf = config.get("benchmark_etf", None)
    gold_signal_index = config.get("gold_signal_index", "$NDX")

    prices = load_prices_for_universe(universe_folder, config)

    # Use benchmark ETF as fallback if index not in prices
    if benchmark_symbol not in prices.columns and benchmark_etf and benchmark_etf in prices.columns:
        benchmark_symbol = benchmark_etf

    print(f"\n{'='*70}")
    print(f"BACKTEST: {universe_name.upper()} Momentum Top {top_n}")
    print(f"Buffer: entry ≤ {entry_rank}, exit > {exit_rank}")
    print(f"Gold rotation: {gold_signal_index}/XAUUSD ≥ {ndx_gold_threshold}")
    print(f"Start year: {start_year}")
    print(f"Benchmark: {benchmark_symbol}")
    print(f"{'='*70}")

    # Generate rebalance dates (monthly)
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

    # Run backtest
    portfolio_value = 100000.0
    monthly_contribution = 1000.0
    total_invested = 100000.0
    holdings_history = []
    current_holdings = set()
    total_trades = 0

    for i, rebal_date in enumerate(rebal_dates):
        next_rebal = rebal_dates[i + 1] if i + 1 < len(rebal_dates) else prices.index[-1]

        # Gold rotation check (using universe-specific index/XAUUSD ratio)
        if ndx_gold_threshold and gold_signal_index in prices.columns and "XAUUSD" in prices.columns:
            idx_p = prices[gold_signal_index].loc[:rebal_date].dropna()
            xau_p = prices["XAUUSD"].loc[:rebal_date].dropna()
            if len(idx_p) > 0 and len(xau_p) > 0:
                ratio = idx_p.iloc[-1] / xau_p.iloc[-1]
                if ratio >= ndx_gold_threshold:
                    hold_period = prices.loc[rebal_date:next_rebal, "XAUUSD"].dropna()
                    gold_ret = (hold_period.iloc[-1] / hold_period.iloc[0] - 1) if len(hold_period) >= 2 else 0
                    portfolio_value *= (1 + gold_ret)
                    portfolio_value += monthly_contribution
                    total_invested += monthly_contribution

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

        # Get universe members
        universe = get_members_at_date(universe_folder, rebal_date.strftime("%Y-%m-%d"))

        # Calculate momentum scores
        scores = calculate_momentum_scores(prices, universe, rebal_date)
        if scores.empty:
            portfolio_value += monthly_contribution
            total_invested += monthly_contribution
            continue

        scores["Rank"] = range(1, len(scores) + 1)
        ranked = dict(zip(scores["Ticker"], scores["Rank"]))

        # Buffer logic
        retained = set()
        for ticker in current_holdings:
            if ticker in ranked and ranked[ticker] <= exit_rank:
                retained.add(ticker)

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
        added = sorted(new_portfolio - current_holdings)
        removed = sorted(current_holdings - new_portfolio)
        total_trades += trades
        current_holdings = new_portfolio

        # Equal weight
        weight = 1.0 / len(new_portfolio) if new_portfolio else 0

        # Calculate returns (base + leveraged ETF where available)
        hold_period = prices.loc[rebal_date:next_rebal]
        if len(hold_period) < 2:
            portfolio_value += monthly_contribution
            total_invested += monthly_contribution
            continue

        period_ret = 0
        ticker_returns = {}
        lev_ticker_returns = {}

        for ticker in new_portfolio:
            if ticker in hold_period.columns:
                tp = hold_period[ticker].dropna()
                if len(tp) >= 2:
                    # Base return
                    ticker_ret = (tp.iloc[-1] / tp.iloc[0]) - 1
                    period_ret += weight * ticker_ret
                    ticker_returns[ticker] = round(ticker_ret * 100, 2)

                    # Leveraged return: use actual ETF if available, else same as base
                    lev_ticker = LEVERAGED_ETF_MAP.get(ticker)
                    if lev_ticker and lev_ticker in hold_period.columns:
                        lp = hold_period[lev_ticker].dropna()
                        if len(lp) >= 2:
                            lev_ret = (lp.iloc[-1] / lp.iloc[0]) - 1
                            lev_ticker_returns[ticker] = round(lev_ret * 100, 2)
                            continue
                    # No leveraged ETF available — use base return
                    lev_ticker_returns[ticker] = ticker_returns[ticker]

        # Leveraged portfolio return (equal-weighted)
        if ticker_returns:
            lev_period_ret = sum(lev_ticker_returns.get(t, 0) for t in new_portfolio) / len(new_portfolio) / 100
        else:
            lev_period_ret = 0

        portfolio_value *= (1 + period_ret)
        portfolio_value += monthly_contribution
        total_invested += monthly_contribution

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
        })

        if i % 50 == 0:
            print(f"  {rebal_date.date()}: Val=${portfolio_value:,.0f} | Held: {sorted(new_portfolio)}")

    # Results
    print(f"\n  Total trades: {total_trades}")
    print(f"  Total invested: ${total_invested:,.0f}")

    # Calculate metrics
    years = (holdings_history[-1]["Next_Rebal"] - holdings_history[0]["Rebal_Date"]).days / 365.25
    multiple = portfolio_value / total_invested

    # XIRR
    cashflows = [(holdings_history[0]["Rebal_Date"], -100000)]
    for h in holdings_history:
        cashflows.append((h["Rebal_Date"], -1000))
    cashflows.append((holdings_history[-1]["Next_Rebal"], portfolio_value))
    xirr_rate = xirr(cashflows)

    # Max drawdown
    port_values = [100000] + [h["Portfolio_Value"] for h in holdings_history]
    mdd, _, _ = max_drawdown(port_values)

    print(f"\n{'='*70}")
    print(f"RESULTS: {universe_name.upper()} Momentum Top {top_n}")
    print(f"  Period: {holdings_history[0]['Rebal_Date'].date()} to {holdings_history[-1]['Next_Rebal'].date()} ({years:.1f} years)")
    print(f"  Total invested: ${total_invested:,.0f}")
    print(f"  Ending value:   ${portfolio_value:,.0f}")
    print(f"  Multiple:       {multiple:.1f}x")
    print(f"  XIRR:           {xirr_rate:.1%}")
    print(f"  Max Drawdown:   -{mdd:.1%}")
    print(f"{'='*70}")

    # Save wide-format CSV
    _save_wide_csv(universe_name, holdings_history, prices, benchmark_symbol)

    return portfolio_value, holdings_history


def _save_wide_csv(universe_name, holdings_history, prices, benchmark_symbol):
    """Save backtest results in wide CSV format for dashboard generation."""
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
        }

        # Benchmark return
        bench_ret = None
        if benchmark_symbol in prices.columns:
            bp = prices.loc[rebal_date:next_rebal, benchmark_symbol].dropna()
            if len(bp) >= 2:
                bench_ret = (bp.iloc[-1] / bp.iloc[0] - 1)
        if bench_ret is None and benchmark_etf and benchmark_etf in prices.columns:
            bp = prices.loc[rebal_date:next_rebal, benchmark_etf].dropna()
            if len(bp) >= 2:
                bench_ret = (bp.iloc[-1] / bp.iloc[0] - 1)
        row["Benchmark_Return_Pct"] = round(bench_ret * 100, 2) if bench_ret is not None else ""

        # Top 10 and changes
        row["Top10"] = ", ".join(h.get("Top10", []))
        added = h.get("Added", [])
        removed = h.get("Removed", [])
        if added and removed:
            row["Changes"] = ", ".join([f"{r}→{a}" for r, a in zip(removed, added)])
        elif added:
            row["Changes"] = "+" + ", +".join(added)
        else:
            row["Changes"] = ""

        # Holdings returns (from precomputed in holdings_history)
        ticker_returns = h.get("Ticker_Returns", {})
        lev_ticker_returns = h.get("Lev_Ticker_Returns", {})
        for holding in h["Holdings"]:
            ticker = holding["Ticker"]
            weight = holding["Weight"]
            if ticker in ticker_returns:
                row[f"{ticker}_Pct"] = round(weight * 100, 2)
                row[f"{ticker}_Ret"] = ticker_returns[ticker]
                row[f"{ticker}_LevRet"] = lev_ticker_returns.get(ticker, ticker_returns[ticker])

        rows.append(row)

    # Save to dashboards/{universe}/ folder
    dashboard_dir = OUTPUT_DIR / "dashboards" / universe_name
    dashboard_dir.mkdir(parents=True, exist_ok=True)
    output_file = dashboard_dir / "backtest_wide.csv"
    pd.DataFrame(rows).to_csv(output_file, index=False)
    print(f"  Saved: {output_file}")


# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Universal Momentum Backtest")
    parser.add_argument("--universe", type=str, required=False, help="Universe to backtest")
    parser.add_argument("--all", action="store_true", help="Run backtest for ALL universes")
    parser.add_argument("--top-n", type=int, default=None, help="Override number of stocks to hold")
    parser.add_argument("--entry-rank", type=int, default=None, help="Override entry rank threshold")
    parser.add_argument("--exit-rank", type=int, default=None, help="Override exit rank threshold")
    parser.add_argument("--gold-threshold", type=float, default=None, help="Override gold threshold")
    parser.add_argument("--start-year", type=int, default=None, help="Override start year")
    parser.add_argument("--list", action="store_true", help="List available universes")
    parser.add_argument("--dashboard", action="store_true", help="Generate HTML dashboard after backtest")
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
