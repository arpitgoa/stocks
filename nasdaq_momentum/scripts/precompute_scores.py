"""
Precompute Momentum Scores for ALL tickers at ALL month-ends.
=============================================================
This creates a single file with raw momentum ratios that can be
filtered by any universe at runtime — making backtests near-instant.

Output: precomputed_momentum.parquet
  Columns: Date, Ticker, MR_12, MR_6, MR_avg (average of MR_12 + MR_6)

Usage:
    python precompute_scores.py           # Compute all
    python precompute_scores.py --verify  # Verify against live calculation

The MR_avg column is what determines rank. Since Z-scoring is monotonic,
ranking by MR_avg gives identical order as ranking by Normalized Score.
"""

import argparse
import numpy as np
import pandas as pd
from pathlib import Path

NORGATE_DIR = Path.home() / "Documents" / "workspace" / "historical-index-universe-data"
PRICES_DIR = NORGATE_DIR / "prices"
OUTPUT_FILE = Path(__file__).parent.parent / "data" / "precomputed_momentum.parquet"

MIN_HISTORY = 252
SKIP_DAYS = 5


def precompute_all_scores():
    """Compute momentum ratios for every ticker at every month-end."""
    
    # Build file map
    print("Indexing price files...")
    file_map = {f.stem.split("__")[0]: f for f in PRICES_DIR.glob("*.csv")}
    print(f"  {len(file_map)} price files found")
    
    # Get all month-end dates from a long-running ticker
    print("Determining month-end dates...")
    # Use $NDX as reference for trading dates
    ref_file = file_map.get("$NDX") or list(file_map.values())[0]
    ref_df = pd.read_csv(ref_file, usecols=["Date"], index_col="Date", parse_dates=True)
    
    # Get last trading day of each month
    month_ends = ref_df.resample("M").last().index
    # Filter to actual trading dates
    all_trading_dates = ref_df.index
    rebal_dates = []
    for me in month_ends:
        # Find last trading day on or before month end
        valid = all_trading_dates[all_trading_dates <= me]
        if len(valid) > 0:
            rebal_dates.append(valid[-1])
    
    print(f"  {len(rebal_dates)} month-ends ({rebal_dates[0].date()} to {rebal_dates[-1].date()})")
    
    # Skip tickers that start with $ (indices) or are non-stock
    skip_prefixes = {"XAUUSD"}  # gold spot, not a stock
    stock_tickers = [t for t in file_map.keys() if not t.startswith("$") and t not in skip_prefixes]
    print(f"  {len(stock_tickers)} stock tickers to process")
    
    # Process each ticker
    all_rows = []
    processed = 0
    
    for ticker in stock_tickers:
        filepath = file_map[ticker]
        
        try:
            df = pd.read_csv(filepath, usecols=["Date", "Close"], index_col="Date", parse_dates=True)
            ts = df["Close"].dropna()
        except Exception:
            continue
        
        if len(ts) < MIN_HISTORY + SKIP_DAYS + 10:
            continue
        
        # For each month-end, calculate momentum ratios
        for rebal_date in rebal_dates:
            data = ts.loc[:rebal_date]
            if len(data) < MIN_HISTORY + SKIP_DAYS:
                continue
            
            end_idx = len(data) - 1 - SKIP_DAYS
            if end_idx < MIN_HISTORY:
                continue
            
            price_end = data.iloc[end_idx]
            price_12m = data.iloc[end_idx - 252] if end_idx >= 252 else None
            price_6m = data.iloc[end_idx - 126] if end_idx >= 126 else None
            
            if price_12m is None or price_6m is None:
                continue
            if price_12m <= 0 or price_6m <= 0 or price_end <= 0:
                continue
            
            ret_12m = price_end / price_12m - 1
            ret_6m = price_end / price_6m - 1
            
            # Annualized volatility
            log_rets = np.log(
                data.iloc[end_idx - 252:end_idx + 1] /
                data.iloc[end_idx - 252:end_idx + 1].shift(1)
            ).dropna()
            
            if len(log_rets) < 100:
                continue
            
            vol = log_rets.std() * np.sqrt(252)
            if vol <= 0:
                continue
            
            mr_12 = ret_12m / vol
            mr_6 = ret_6m / vol
            mr_avg = (mr_12 + mr_6) / 2
            
            all_rows.append({
                "Date": rebal_date,
                "Ticker": ticker,
                "MR_12": round(mr_12, 6),
                "MR_6": round(mr_6, 6),
                "MR_avg": round(mr_avg, 6),
            })
        
        processed += 1
        if processed % 500 == 0:
            print(f"  Processed {processed}/{len(stock_tickers)} tickers ({len(all_rows):,} data points)...")
    
    print(f"  Processed {processed}/{len(stock_tickers)} tickers")
    print(f"  Total data points: {len(all_rows):,}")
    
    # Create DataFrame and save
    scores_df = pd.DataFrame(all_rows)
    scores_df["Date"] = pd.to_datetime(scores_df["Date"])
    scores_df = scores_df.sort_values(["Date", "MR_avg"], ascending=[True, False]).reset_index(drop=True)
    
    # Save
    try:
        scores_df.to_parquet(OUTPUT_FILE, index=False)
        print(f"\nSaved: {OUTPUT_FILE}")
    except ImportError:
        csv_fallback = OUTPUT_FILE.with_suffix(".csv")
        scores_df.to_csv(csv_fallback, index=False)
        print(f"\nSaved (CSV fallback): {csv_fallback}")
    
    print(f"  Shape: {scores_df.shape[0]:,} rows × {scores_df.shape[1]} columns")
    file_to_check = OUTPUT_FILE if OUTPUT_FILE.exists() else OUTPUT_FILE.with_suffix(".csv")
    print(f"  File size: {file_to_check.stat().st_size / 1024 / 1024:.1f} MB")
    
    return scores_df


def verify_against_live(universe="nasdaq100"):
    """Verify precomputed scores match live calculation for a universe."""
    from universe_config import get_config
    from run_backtest import load_membership, get_members_at_date, calculate_momentum_scores, _get_price_file_map, load_prices_for_universe
    
    config = get_config(universe)
    
    print(f"\nVerifying precomputed scores against live for {universe}...")
    
    # Load precomputed
    scores_df = pd.read_parquet(OUTPUT_FILE)
    
    # Load prices for live calculation
    prices = load_prices_for_universe(config["folder"], config)
    
    # Check a few random months
    test_dates = scores_df["Date"].unique()
    # Pick 5 spread across the range
    test_indices = np.linspace(100, len(test_dates) - 10, 5, dtype=int)
    
    mismatches = 0
    total_checked = 0
    
    for idx in test_indices:
        rebal_date = pd.Timestamp(test_dates[idx])
        
        # Get universe members
        members = get_members_at_date(config["folder"], rebal_date.strftime("%Y-%m-%d"))
        
        # Live calculation
        live_scores = calculate_momentum_scores(prices, members, rebal_date)
        if live_scores.empty:
            continue
        live_ranking = live_scores["Ticker"].tolist()[:10]
        
        # Precomputed
        month_scores = scores_df[scores_df["Date"] == rebal_date]
        # Filter to universe members
        universe_scores = month_scores[month_scores["Ticker"].isin(members)]
        precomp_ranking = universe_scores.sort_values("MR_avg", ascending=False)["Ticker"].tolist()[:10]
        
        # Compare top 10
        match = live_ranking == precomp_ranking
        total_checked += 1
        
        if not match:
            mismatches += 1
            print(f"  {rebal_date.date()}: MISMATCH")
            print(f"    Live top 10:    {live_ranking}")
            print(f"    Precomp top 10: {precomp_ranking}")
        else:
            print(f"  {rebal_date.date()}: ✓ Match (top 10 identical)")
    
    print(f"\nVerification: {total_checked - mismatches}/{total_checked} months match perfectly")
    if mismatches == 0:
        print("✓ PRECOMPUTED SCORES ARE IDENTICAL TO LIVE CALCULATION")
    else:
        print(f"⚠️ {mismatches} mismatches found — investigate!")


def main():
    parser = argparse.ArgumentParser(description="Precompute momentum scores")
    parser.add_argument("--verify", action="store_true", help="Verify against live calculation")
    parser.add_argument("--universe", type=str, default="nasdaq100", help="Universe to verify against")
    args = parser.parse_args()
    
    if args.verify:
        if not OUTPUT_FILE.exists():
            print(f"Error: {OUTPUT_FILE} not found. Run without --verify first.")
            return
        verify_against_live(args.universe)
    else:
        precompute_all_scores()


if __name__ == "__main__":
    main()
