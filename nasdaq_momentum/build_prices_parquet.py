"""
Build a single parquet file with all Close prices from Norgate CSVs.
================================================================
This replaces reading 20K individual CSVs with one fast parquet read.

Usage:
    python build_prices_parquet.py              # Full rebuild
    python build_prices_parquet.py --incremental  # Only add new dates/tickers

Output: all_prices.parquet (Date index × ticker columns, Close prices only)

Monthly workflow:
    1. Sync new CSVs from Windows VM
    2. python build_prices_parquet.py --incremental
    3. python run_backtest.py --all --dashboard
"""

import argparse
import pandas as pd
from pathlib import Path
import time

NORGATE_DIR = Path.home() / "Documents" / "workspace" / "historical-index-universe-data"
PRICES_DIR = NORGATE_DIR / "prices"
OUTPUT_FILE = Path(__file__).parent / "all_prices.parquet"


def build_full():
    """Full rebuild: read ALL CSVs and create parquet."""
    print("Building full prices parquet...")
    t0 = time.time()

    price_files = sorted(PRICES_DIR.glob("*.csv"))
    print(f"  Found {len(price_files)} price files")

    all_close = {}
    processed = 0

    for f in price_files:
        symbol = f.stem.split("__")[0]
        try:
            df = pd.read_csv(f, usecols=["Date", "Close"], index_col="Date", parse_dates=True)
            all_close[symbol] = df["Close"]
            processed += 1
        except Exception as e:
            continue

        if processed % 2000 == 0:
            print(f"  Processed {processed}/{len(price_files)} files...")

    print(f"  Processed {processed} files total")

    prices = pd.DataFrame(all_close)
    prices.sort_index(inplace=True)
    prices.index.name = "Date"

    print(f"  DataFrame: {prices.shape[0]} days × {prices.shape[1]} tickers")
    print(f"  Date range: {prices.index[0].date()} to {prices.index[-1].date()}")

    # Save as parquet
    prices.to_parquet(OUTPUT_FILE)

    elapsed = time.time() - t0
    file_size = OUTPUT_FILE.stat().st_size / 1024 / 1024
    print(f"\nSaved: {OUTPUT_FILE}")
    print(f"  Size: {file_size:.1f} MB")
    print(f"  Time: {elapsed:.1f} seconds")


def build_incremental():
    """Incremental: only add new dates and new tickers."""
    if not OUTPUT_FILE.exists():
        print("No existing parquet found. Running full build.")
        build_full()
        return

    print("Incremental update...")
    t0 = time.time()

    # Load existing
    existing = pd.read_parquet(OUTPUT_FILE)
    last_date = existing.index[-1]
    existing_tickers = set(existing.columns)
    print(f"  Existing: {existing.shape[0]} days × {existing.shape[1]} tickers (last: {last_date.date()})")

    # Find all current CSV files
    price_files = {f.stem.split("__")[0]: f for f in PRICES_DIR.glob("*.csv")}
    all_tickers = set(price_files.keys())

    # New tickers (not in parquet)
    new_tickers = all_tickers - existing_tickers
    print(f"  New tickers to add: {len(new_tickers)}")

    # Load new ticker data fully
    new_data = {}
    for ticker in new_tickers:
        try:
            df = pd.read_csv(price_files[ticker], usecols=["Date", "Close"], index_col="Date", parse_dates=True)
            new_data[ticker] = df["Close"]
        except Exception:
            continue

    # Load new dates for existing tickers
    updated_data = {}
    updated_count = 0
    for ticker in existing_tickers:
        if ticker not in price_files:
            continue
        try:
            df = pd.read_csv(price_files[ticker], usecols=["Date", "Close"], index_col="Date", parse_dates=True)
            # Only rows after last_date
            new_rows = df[df.index > last_date]
            if len(new_rows) > 0:
                updated_data[ticker] = new_rows["Close"]
                updated_count += 1
        except Exception:
            continue

    print(f"  Existing tickers with new dates: {updated_count}")

    if not new_data and not updated_data:
        print("  Nothing to update. Parquet is current.")
        return

    # Build updates
    if new_data:
        new_df = pd.DataFrame(new_data)
        existing = existing.join(new_df, how="outer")

    if updated_data:
        update_df = pd.DataFrame(updated_data)
        # Append new date rows
        combined_idx = existing.index.union(update_df.index)
        existing = existing.reindex(combined_idx)
        # Fill in the new values
        for ticker, series in updated_data.items():
            existing.loc[series.index, ticker] = series.values

    existing.sort_index(inplace=True)

    # Save
    existing.to_parquet(OUTPUT_FILE)

    elapsed = time.time() - t0
    file_size = OUTPUT_FILE.stat().st_size / 1024 / 1024
    print(f"\nSaved: {OUTPUT_FILE}")
    print(f"  Size: {file_size:.1f} MB")
    print(f"  Shape: {existing.shape[0]} days × {existing.shape[1]} tickers")
    print(f"  Time: {elapsed:.1f} seconds")


def main():
    parser = argparse.ArgumentParser(description="Build prices parquet from Norgate CSVs")
    parser.add_argument("--incremental", action="store_true", help="Only add new dates/tickers")
    args = parser.parse_args()

    if args.incremental:
        build_incremental()
    else:
        build_full()


if __name__ == "__main__":
    main()
