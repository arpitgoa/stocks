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

_prices_cache = None
_membership_cache = {}


def load_prices():
    """Load all Norgate price CSVs into a single Close price DataFrame."""
    global _prices_cache
    if _prices_cache is not None:
        return _prices_cache

    print("Loading Norgate price data...")
    price_files = sorted(PRICES_DIR.glob("*.csv"))
    print(f"  Found {len(price_files)} price files")

    all_close = {}
    for f in price_files:
        symbol = f.stem.split("__")[0]
        df = pd.read_csv(f, usecols=["Date", "Close"], index_col="Date", parse_dates=True)
        all_close[symbol] = df["Close"]

    prices = pd.DataFrame(all_close).sort_index()
    print(f"  Combined: {prices.shape[0]} days × {prices.shape[1]} tickers")
    print(f"  Date range: {prices.index[0].date()} to {prices.index[-1].date()}")

    _prices_cache = prices
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

def calculate_momentum_scores(prices_df, universe_tickers, rebal_date,
                              min_history=252, skip_days=5):
    """
    Calculate Normalized Momentum Score for all eligible tickers.
    Same NSE methodology as the NASDAQ-100 strategy.
    """
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

        # Annualized volatility
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
            "Return_12M": ret_12m,
            "Return_6M": ret_6m,
            "Volatility": vol,
            "MR_12": mr_12,
            "MR_6": mr_6,
        })

    if not results:
        return pd.DataFrame()

    df = pd.DataFrame(results)

    # Z-scores across universe
    df["Z_12"] = (df["MR_12"] - df["MR_12"].mean()) / df["MR_12"].std()
    df["Z_6"] = (df["MR_6"] - df["MR_6"].mean()) / df["MR_6"].std()
    df["Weighted_Z"] = 0.5 * df["Z_12"] + 0.5 * df["Z_6"]

    # Normalized score
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

    prices = load_prices()

    # Ensure we have gold signal index and XAUUSD for gold rotation
    for idx_symbol in [gold_signal_index, "$NDX"]:
        if idx_symbol not in prices.columns:
            files = list(PRICES_DIR.glob(f"{idx_symbol}__*.csv"))
            if files:
                idx_df = pd.read_csv(files[0], usecols=["Date", "Close"], index_col="Date", parse_dates=True)
                prices[idx_symbol] = idx_df["Close"]

    if "XAUUSD" not in prices.columns:
        xau_file = list(PRICES_DIR.glob("XAUUSD__*.csv"))
        if xau_file:
            xau_df = pd.read_csv(xau_file[0], usecols=["Date", "Close"], index_col="Date", parse_dates=True)
            prices["XAUUSD"] = xau_df["Close"]

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
                        "Portfolio_Value": portfolio_value,
                        "Holdings": [{"Ticker": "XAUUSD", "Weight": 1.0}],
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

        # Calculate return
        hold_period = prices.loc[rebal_date:next_rebal]
        if len(hold_period) < 2:
            portfolio_value += monthly_contribution
            total_invested += monthly_contribution
            continue

        period_ret = 0
        for ticker in new_portfolio:
            if ticker in hold_period.columns:
                tp = hold_period[ticker].dropna()
                if len(tp) >= 2:
                    period_ret += weight * ((tp.iloc[-1] / tp.iloc[0]) - 1)

        portfolio_value *= (1 + period_ret)
        portfolio_value += monthly_contribution
        total_invested += monthly_contribution

        holdings_history.append({
            "Rebal_Date": rebal_date,
            "Next_Rebal": next_rebal,
            "Period_Return": period_ret,
            "Portfolio_Value": portfolio_value,
            "Holdings": [{"Ticker": t, "Weight": weight} for t in sorted(new_portfolio)],
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

        # Holdings returns
        hold_period = prices.loc[rebal_date:next_rebal]
        for holding in h["Holdings"]:
            ticker = holding["Ticker"]
            weight = holding["Weight"]
            if ticker in hold_period.columns:
                tp = hold_period[ticker].dropna()
                if len(tp) >= 2:
                    ret = round(((tp.iloc[-1] / tp.iloc[0]) - 1) * 100, 2)
                    row[f"{ticker}_Pct"] = round(weight * 100, 2)
                    row[f"{ticker}_Ret"] = ret

        rows.append(row)

    output_file = OUTPUT_DIR / f"{universe_name}_backtest_wide.csv"
    pd.DataFrame(rows).to_csv(output_file, index=False)
    print(f"  Saved: {output_file}")


# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Universal Momentum Backtest")
    parser.add_argument("--universe", type=str, required=False, help="Universe to backtest")
    parser.add_argument("--top-n", type=int, default=None, help="Override number of stocks to hold")
    parser.add_argument("--entry-rank", type=int, default=None, help="Override entry rank threshold")
    parser.add_argument("--exit-rank", type=int, default=None, help="Override exit rank threshold")
    parser.add_argument("--gold-threshold", type=float, default=None, help="Override NDX/XAUUSD threshold")
    parser.add_argument("--start-year", type=int, default=None, help="Override start year")
    parser.add_argument("--list", action="store_true", help="List available universes")
    parser.add_argument("--dashboard", action="store_true", help="Generate HTML dashboard after backtest")
    args = parser.parse_args()

    if args.list:
        list_universes()
        return

    if not args.universe:
        print("Error: --universe required. Use --list to see options.")
        return

    if args.universe not in UNIVERSE_CONFIGS:
        print(f"Unknown universe: {args.universe}. Use --list to see options.")
        return

    run_backtest(
        universe_name=args.universe,
        top_n=args.top_n,
        entry_rank=args.entry_rank,
        exit_rank=args.exit_rank,
        ndx_gold_threshold=args.gold_threshold,
        start_year=args.start_year,
    )

    if args.dashboard:
        print("\nGenerating dashboard...")
        os.system(f"python generate_dashboard.py --universe {args.universe}")


if __name__ == "__main__":
    main()
