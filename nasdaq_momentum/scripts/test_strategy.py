#!/usr/bin/env python3
"""
Strategy Parameter Testing Script
===================================
Runs the backtest with various parameter combinations and outputs a comparison table.
Use this to validate changes before committing to production config.

Usage:
    python scripts/test_strategy.py                          # Test nasdaq100_vix (default)
    python scripts/test_strategy.py --universe sp500         # Test SP500
    python scripts/test_strategy.py --universe nasdaq100_vix --period 2015-2026
    python scripts/test_strategy.py --full                   # Test all universes

Output: Prints a comparison table of CAGR, Max DD, ending value for each parameter set.
"""

import sys
import argparse
import numpy as np
import pandas as pd
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.data_loader import load_prices_for_universe, build_membership_lookup
from core.momentum import _get_precomputed_by_date
from core.metrics import max_drawdown
from universe_config import get_config, UNIVERSE_CONFIGS
from leveraged_config import LEVERAGED_ETF_MAP


# ============================================================
# CORE TEST ENGINE
# ============================================================

def score_blend(prices, universe_tickers, cutoff_idx, w12, w6, use_fast=False):
    """Score with configurable blend weights."""
    skip_days = 5
    lb_long, lb_short = (126, 42) if use_fast else (252, 126)
    results = []
    for ticker in universe_tickers:
        if ticker not in prices.columns:
            continue
        ts = prices[ticker].iloc[:cutoff_idx + 1].dropna()
        end_idx = len(ts) - 1 - skip_days
        if end_idx < lb_long:
            continue
        price_end = ts.iloc[end_idx]
        price_long = ts.iloc[end_idx - lb_long]
        price_short = ts.iloc[end_idx - lb_short]
        if price_long <= 0 or price_short <= 0:
            continue
        log_rets = np.log(
            ts.iloc[end_idx - lb_long:end_idx + 1] /
            ts.iloc[end_idx - lb_long:end_idx + 1].shift(1)
        ).dropna()
        if len(log_rets) < 50:
            continue
        vol = log_rets.std() * np.sqrt(252)
        if vol <= 0:
            continue
        results.append({
            "Ticker": ticker,
            "MR_12": (price_end / price_long - 1) / vol,
            "MR_6": (price_end / price_short - 1) / vol,
        })
    if not results:
        return pd.DataFrame()
    df = pd.DataFrame(results)
    df["Z_12"] = (df["MR_12"] - df["MR_12"].mean()) / df["MR_12"].std()
    df["Z_6"] = (df["MR_6"] - df["MR_6"].mean()) / df["MR_6"].std()
    df["Weighted_Z"] = w12 * df["Z_12"] + w6 * df["Z_6"]
    df["Momentum_Score"] = df["Weighted_Z"].apply(lambda z: (1 + z) if z >= 0 else 1 / (1 - z))
    return df.sort_values("Momentum_Score", ascending=False).reset_index(drop=True)


def run_backtest_test(prices, rebal_dates, date_to_idx, membership_lookup,
                      top_n, entry_rank, exit_rank, gold_threshold, gold_signal_index,
                      blend_normal=(0.7, 0.3), blend_vix=(0.5, 0.5), vix_threshold=None,
                      start_filter=None, end_filter=None):
    """
    Run a single backtest with given parameters. Returns metrics dict.
    No DCA — pure lump sum $100k for clean comparison.
    """
    portfolio_value = 100000.0
    current_holdings = set()
    returns_list = []

    for i, rebal_date in enumerate(rebal_dates):
        if start_filter and rebal_date < pd.Timestamp(start_filter):
            continue
        if end_filter and rebal_date > pd.Timestamp(end_filter):
            continue

        next_rebal = rebal_dates[i + 1] if i + 1 < len(rebal_dates) else prices.index[-1]
        cutoff_idx = date_to_idx[rebal_date]

        # Gold rotation check
        gold_triggered = False
        if gold_threshold and gold_signal_index in prices.columns and "XAUUSD" in prices.columns:
            idx_p = prices[gold_signal_index].iloc[:cutoff_idx + 1].dropna()
            xau_p = prices["XAUUSD"].iloc[:cutoff_idx + 1].dropna()
            if len(idx_p) > 0 and len(xau_p) > 0:
                if idx_p.iloc[-1] / xau_p.iloc[-1] >= gold_threshold:
                    gold_triggered = True

        if gold_triggered:
            next_idx = prices.index.searchsorted(next_rebal)
            hp = prices["XAUUSD"].iloc[cutoff_idx:next_idx + 1].dropna()
            gold_ret = (hp.iloc[-1] / hp.iloc[0] - 1) if len(hp) >= 2 else 0
            portfolio_value *= (1 + gold_ret)
            current_holdings = set()
            returns_list.append(gold_ret)
            continue

        # VIX check
        use_fast = False
        if vix_threshold and "$VIX" in prices.columns:
            vix_ts = prices["$VIX"].loc[:rebal_date].dropna()
            if len(vix_ts) > 0 and vix_ts.iloc[-1] > vix_threshold:
                use_fast = True

        # Score
        w12, w6 = blend_vix if use_fast else blend_normal
        universe = membership_lookup[rebal_date]
        scores = score_blend(prices, universe, cutoff_idx, w12, w6, use_fast)

        if scores.empty:
            returns_list.append(0)
            continue

        # Buffer logic
        scores["Rank"] = range(1, len(scores) + 1)
        ranked = dict(zip(scores["Ticker"], scores["Rank"]))
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

        current_holdings = new_portfolio
        weight = 1.0 / len(new_portfolio) if new_portfolio else 0
        next_idx = prices.index.searchsorted(next_rebal)
        hold_slice = prices.iloc[cutoff_idx:next_idx + 1]

        if len(hold_slice) < 2:
            returns_list.append(0)
            continue

        period_ret = 0
        for t in new_portfolio:
            if t in hold_slice.columns:
                tp = hold_slice[t].dropna()
                if len(tp) >= 2:
                    period_ret += weight * (tp.iloc[-1] / tp.iloc[0] - 1)

        portfolio_value *= (1 + period_ret)
        returns_list.append(period_ret)

    if not returns_list:
        return None

    years = len(returns_list) / 12
    pv = [100000]
    for r in returns_list:
        pv.append(pv[-1] * (1 + r))
    mdd, _, _ = max_drawdown(pv)
    cagr = ((portfolio_value / 100000) ** (1 / years) - 1) * 100

    return {
        "cagr": cagr,
        "max_dd": mdd * 100,
        "ending_value": portfolio_value,
        "years": years,
        "months": len(returns_list),
        "multiple": portfolio_value / 100000,
        "_returns": returns_list,
    }


# ============================================================
# TEST SUITES
# ============================================================

def _print_rolling_returns(monthly_returns, verbose=True):
    """Calculate and print rolling return statistics for 3, 5, 10, 15, 20 year windows."""
    if not monthly_returns:
        print("  No data for rolling analysis.")
        return

    windows = [
        (3, "3-Year"),
        (5, "5-Year"),
        (10, "10-Year"),
        (15, "15-Year"),
        (20, "20-Year"),
    ]

    print(f"\n  {'Window':<10} {'Periods':>8} {'Min CAGR':>9} {'Median':>8} {'Avg':>8} {'Max CAGR':>9} {'% > 0':>7} {'% > 15%':>8}")
    print(f"  {'-'*70}")

    for years, label in windows:
        months_needed = years * 12
        if len(monthly_returns) < months_needed:
            print(f"  {label:<10} {'—':>8} (need {months_needed} months, have {len(monthly_returns)})")
            continue

        rolling_cagrs = []
        for start in range(len(monthly_returns) - months_needed + 1):
            window = monthly_returns[start:start + months_needed]
            compound = 1.0
            for r in window:
                compound *= (1 + r)
            cagr = (compound ** (1 / years) - 1) * 100
            rolling_cagrs.append(cagr)

        if not rolling_cagrs:
            continue

        arr = np.array(rolling_cagrs)
        min_cagr = arr.min()
        max_cagr = arr.max()
        avg_cagr = arr.mean()
        med_cagr = np.median(arr)
        pct_pos = (arr > 0).sum() / len(arr) * 100
        pct_15 = (arr > 15).sum() / len(arr) * 100

        print(f"  {label:<10} {len(rolling_cagrs):>8} {min_cagr:>+8.1f}% {med_cagr:>+7.1f}% {avg_cagr:>+7.1f}% {max_cagr:>+8.1f}% {pct_pos:>6.0f}% {pct_15:>7.0f}%")

    # Worst and best periods
    print(f"\n  {'Window':<10} {'Worst Period':<25} {'Best Period':<25}")
    print(f"  {'-'*60}")
    for years, label in windows:
        months_needed = years * 12
        if len(monthly_returns) < months_needed:
            continue

        rolling_cagrs = []
        for start in range(len(monthly_returns) - months_needed + 1):
            window = monthly_returns[start:start + months_needed]
            compound = 1.0
            for r in window:
                compound *= (1 + r)
            cagr = (compound ** (1 / years) - 1) * 100
            rolling_cagrs.append(cagr)

        if not rolling_cagrs:
            continue

        worst_idx = np.argmin(rolling_cagrs)
        best_idx = np.argmax(rolling_cagrs)
        # Approximate start month (offset from beginning of returns list)
        worst_start_month = worst_idx  # months from start of data
        best_start_month = best_idx

        print(f"  {label:<10} {rolling_cagrs[worst_idx]:>+6.1f}% (starting month {worst_start_month+1:>3}) {rolling_cagrs[best_idx]:>+6.1f}% (starting month {best_start_month+1:>3})")


def test_universe(universe_name, start_filter=None, end_filter=None, verbose=True):
    """Run parameter sweep for a universe and print results."""
    config = get_config(universe_name)
    gold_signal_index = config.get("gold_signal_index", "$NDX")

    if verbose:
        print(f"\n{'='*90}")
        print(f"  PARAMETER TEST: {universe_name.upper()}")
        period_str = f"{start_filter or config['start_year']} to {end_filter or 'present'}"
        print(f"  Period: {period_str}")
        print(f"{'='*90}\n")

    # Load data
    lev_tickers = set(LEVERAGED_ETF_MAP.values())
    prices = load_prices_for_universe(config["folder"], config, lev_tickers)

    start_year = config["start_year"]
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

    membership_lookup = build_membership_lookup(config["folder"], rebal_dates)
    _get_precomputed_by_date()
    date_to_idx = {d: prices.index.searchsorted(d) for d in rebal_dates}

    # Current config as baseline
    current_blend = config.get("momentum_blend", (0.7, 0.3))
    current_vix_blend = config.get("vix_momentum_blend", (0.5, 0.5))
    vix_threshold = config.get("vix_threshold", None)
    top_n = config["top_n"]
    entry_rank = config["entry_rank"]
    exit_rank = config["exit_rank"]
    gold_threshold = config["gold_threshold"]

    results = []
    returns_list_store = []  # Store monthly returns for rolling analysis

    def run_and_record(label, **kwargs):
        params = {
            "top_n": top_n, "entry_rank": entry_rank, "exit_rank": exit_rank,
            "gold_threshold": gold_threshold, "gold_signal_index": gold_signal_index,
            "blend_normal": current_blend, "blend_vix": current_vix_blend,
            "vix_threshold": vix_threshold,
            "start_filter": start_filter, "end_filter": end_filter,
        }
        params.update(kwargs)
        result = run_backtest_test(prices, rebal_dates, date_to_idx, membership_lookup, **params)
        if result:
            result["label"] = label
            results.append(result)
            # Store returns for the first run (baseline) for rolling analysis
            if len(results) == 1:
                returns_list_store.append(result.get("_returns", []))

    # --- BASELINE ---
    run_and_record("★ CURRENT CONFIG")

    # --- BLEND VARIATIONS ---
    run_and_record("Blend 50/50", blend_normal=(0.5, 0.5))
    run_and_record("Blend 60/40", blend_normal=(0.6, 0.4))
    run_and_record("Blend 70/30", blend_normal=(0.7, 0.3))
    run_and_record("Blend 80/20", blend_normal=(0.8, 0.2))

    # --- BUFFER VARIATIONS ---
    run_and_record(f"Buffer {top_n}/{exit_rank-5}", exit_rank=exit_rank - 5)
    run_and_record(f"Buffer {top_n}/{exit_rank}", exit_rank=exit_rank)
    run_and_record(f"Buffer {top_n}/{exit_rank+5}", exit_rank=exit_rank + 5)

    # --- GOLD THRESHOLD ---
    if gold_threshold > 0:
        run_and_record(f"Gold {gold_threshold - 0.5:.1f}", gold_threshold=gold_threshold - 0.5)
        run_and_record(f"Gold {gold_threshold:.1f} (current)", gold_threshold=gold_threshold)
        run_and_record(f"Gold {gold_threshold + 0.5:.1f}", gold_threshold=gold_threshold + 0.5)
        run_and_record("No gold", gold_threshold=0)

    # --- VIX BLEND (if applicable) ---
    if vix_threshold:
        run_and_record("VIX blend 30/70", blend_vix=(0.3, 0.7))
        run_and_record("VIX blend 50/50", blend_vix=(0.5, 0.5))
        run_and_record("VIX blend 70/30", blend_vix=(0.7, 0.3))

    # Print results table
    if verbose and results:
        print(f"{'Label':<30} {'CAGR':>7} {'Max DD':>8} {'Multiple':>9} {'Months':>7}")
        print("-" * 65)
        baseline = results[0]
        for r in results:
            cagr_marker = " ✓" if r["cagr"] > baseline["cagr"] + 0.5 else (" ✗" if r["cagr"] < baseline["cagr"] - 0.5 else "")
            dd_marker = " ✓" if r["max_dd"] < baseline["max_dd"] - 1 else (" ✗" if r["max_dd"] > baseline["max_dd"] + 1 else "")
            marker = "★" if r["label"].startswith("★") else " "
            print(f"{marker}{r['label']:<29} {r['cagr']:>6.1f}% {-r['max_dd']:>7.1f}%{dd_marker:<3} {r['multiple']:>7.0f}x {r['months']:>6}")

        # Rolling return analysis for baseline
        print(f"\n{'─'*65}")
        print(f"  ROLLING RETURNS — {results[0]['label']}")
        print(f"{'─'*65}")
        _print_rolling_returns(returns_list_store[0], verbose=True)

    return results


# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Strategy Parameter Tester")
    parser.add_argument("--universe", type=str, default="nasdaq100_vix", help="Universe to test")
    parser.add_argument("--period", type=str, default=None, help="Period filter: 2015-2026 or 2007-2020")
    parser.add_argument("--full", action="store_true", help="Test all universes")
    args = parser.parse_args()

    start_filter = None
    end_filter = None
    if args.period:
        parts = args.period.split("-")
        if len(parts) == 2:
            start_filter = f"{parts[0]}-01-01"
            end_filter = f"{parts[1]}-12-31"

    if args.full:
        for name in sorted(UNIVERSE_CONFIGS.keys()):
            try:
                test_universe(name, start_filter, end_filter)
            except Exception as e:
                print(f"  ❌ {name}: {e}")
    else:
        if args.universe not in UNIVERSE_CONFIGS:
            print(f"Unknown universe: {args.universe}. Available: {', '.join(sorted(UNIVERSE_CONFIGS.keys()))}")
            return
        test_universe(args.universe, start_filter, end_filter)


if __name__ == "__main__":
    main()
