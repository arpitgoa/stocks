"""
Load Norgate price data and SCD2 membership for the NASDAQ-100 backtest.
Replaces the old nasdaq100_daily_closes.csv + nasdaq100_membership_by_year.json
with the more precise Norgate data going back to 1993.

Usage:
    from load_norgate_data import load_prices, get_members_at_date

    prices = load_prices()  # DataFrame: DatetimeIndex × tickers, Close prices
    members = get_members_at_date('2000-03-15')  # list of active tickers
"""

import os
import pandas as pd
from pathlib import Path

# Paths
NORGATE_DIR = Path.home() / "Documents" / "workspace" / "historical-index-universe-data"
PRICES_DIR = NORGATE_DIR / "prices"
MEMBERSHIP_FILE = NORGATE_DIR / "universes" / "nasdaq100" / "membership_periods.csv"

# Cache
_prices_cache = None
_membership_cache = None


def load_prices(include_ohlc=False):
    """
    Load all Norgate price CSVs into a single DataFrame.
    
    Default: returns Close prices only (DatetimeIndex × ticker columns).
    If include_ohlc=True, returns a dict of DataFrames: {'Open': df, 'High': df, 'Low': df, 'Close': df}
    """
    global _prices_cache
    
    if _prices_cache is not None:
        return _prices_cache
    
    print("Loading Norgate price data...")
    
    price_files = sorted(PRICES_DIR.glob("*.csv"))
    print(f"  Found {len(price_files)} price files")
    
    all_close = {}
    all_open = {}
    all_high = {}
    all_low = {}
    
    for f in price_files:
        # Filename format: SYMBOL__ASSETID.csv
        parts = f.stem.split("__")
        symbol = parts[0]
        
        df = pd.read_csv(f, usecols=["Date", "Open", "High", "Low", "Close"], 
                         index_col="Date", parse_dates=True)
        
        all_close[symbol] = df["Close"]
        if include_ohlc:
            all_open[symbol] = df["Open"]
            all_high[symbol] = df["High"]
            all_low[symbol] = df["Low"]
    
    prices = pd.DataFrame(all_close)
    prices.sort_index(inplace=True)
    
    print(f"  Combined: {prices.shape[0]} days × {prices.shape[1]} tickers")
    print(f"  Date range: {prices.index[0].date()} to {prices.index[-1].date()}")
    
    if include_ohlc:
        result = {
            "Open": pd.DataFrame(all_open).sort_index(),
            "High": pd.DataFrame(all_high).sort_index(),
            "Low": pd.DataFrame(all_low).sort_index(),
            "Close": prices,
        }
        _prices_cache = result
        return result
    
    _prices_cache = prices
    return prices


def _load_membership():
    """Load and cache the SCD2 membership periods."""
    global _membership_cache
    
    if _membership_cache is not None:
        return _membership_cache
    
    df = pd.read_csv(MEMBERSHIP_FILE)
    df["EntryDate"] = pd.to_datetime(df["EntryDate"])
    df["ExitDate"] = pd.to_datetime(df["ExitDate"])
    
    _membership_cache = df
    return df


def get_members_at_date(date_str):
    """
    Get list of NASDAQ-100 constituent tickers active on a given date.
    Uses SCD2 membership_periods.csv for exact day-level membership.
    
    Args:
        date_str: date string like '2000-03-15' or a Timestamp
        
    Returns:
        list of ticker symbols active on that date
    """
    df = _load_membership()
    
    if isinstance(date_str, str):
        check_date = pd.Timestamp(date_str)
    else:
        check_date = pd.Timestamp(date_str)
    
    active = df[
        (df["EntryDate"] <= check_date) & 
        ((df["ExitDate"].isna()) | (df["ExitDate"] > check_date))
    ]
    
    return active["Symbol"].tolist()


if __name__ == "__main__":
    # Quick test
    prices = load_prices()
    
    print()
    print("Membership check:")
    for date in ["1994-01-01", "2000-03-10", "2008-09-15", "2020-03-20", "2026-07-01"]:
        members = get_members_at_date(date)
        print(f"  {date}: {len(members)} members, sample: {members[:5]}")
