"""
Data Loading Module
====================
Handles loading price data from parquet/CSV and membership data.
Includes caching to avoid reloading on repeated calls.
"""

import pandas as pd
from pathlib import Path
from .paths import PRICES_DIR, UNIVERSES_DIR, PRICES_PARQUET, LEGACY_CLOSES_CSV


# ============================================================
# CACHES
# ============================================================

_all_prices_cache = None
_membership_cache = {}


# ============================================================
# PRICE LOADING
# ============================================================

def load_all_prices():
    """Load the full prices parquet file. Cached after first call."""
    global _all_prices_cache
    if _all_prices_cache is None:
        if not PRICES_PARQUET.exists():
            return None
        print(f"  Loading prices from parquet ({PRICES_PARQUET.stat().st_size // 1024 // 1024} MB)...")
        _all_prices_cache = pd.read_parquet(PRICES_PARQUET)
        print(f"  Loaded: {_all_prices_cache.shape[0]} days × {_all_prices_cache.shape[1]} tickers")
    return _all_prices_cache


def load_prices_for_universe(universe_folder, config, leveraged_tickers=None):
    """
    Load price data filtered to tickers needed for a specific universe backtest.
    
    Args:
        universe_folder: Folder name under universes/ (e.g., 'nasdaq100')
        config: Universe config dict (needs gold_signal_index, benchmark, benchmark_etf)
        leveraged_tickers: Set of leveraged ETF tickers to include
        
    Returns:
        DataFrame with date index and ticker columns
    """
    membership = load_membership(universe_folder)
    universe_tickers = set(membership["Symbol"].unique())

    # Extra tickers needed for signals and benchmarks
    extra_tickers = {"XAUUSD", "$VIX"}
    extra_tickers.add(config.get("gold_signal_index", "$NDX"))
    extra_tickers.add(config.get("benchmark", ""))
    extra_tickers.add(config.get("benchmark_etf", ""))
    extra_tickers.discard("")

    lev_tickers = leveraged_tickers or set()
    all_needed = universe_tickers | extra_tickers | lev_tickers

    # Try parquet first (fast path)
    all_prices = load_all_prices()
    if all_prices is not None:
        available = [t for t in all_needed if t in all_prices.columns]
        prices = all_prices[available].copy()
        print(f"  Filtered: {len(available)} tickers for {universe_folder}")

        # Try loading leveraged ETFs from legacy CSV if missing from parquet
        if LEGACY_CLOSES_CSV.exists() and lev_tickers:
            missing_lev = [t for t in lev_tickers if t not in prices.columns]
            if missing_lev:
                lev_df = pd.read_csv(LEGACY_CLOSES_CSV, index_col="Date", parse_dates=True)
                added = 0
                for ticker in missing_lev:
                    if ticker in lev_df.columns:
                        prices[ticker] = lev_df[ticker]
                        added += 1
                if added:
                    print(f"  Added {added} leveraged ETFs from yfinance data")
        return prices

    # Fallback: individual CSVs (slow path)
    print("  Falling back to individual CSV loading...")
    file_map = {f.stem.split("__")[0]: f for f in PRICES_DIR.glob("*.csv")}
    all_close = {}
    for ticker in all_needed:
        if ticker in file_map:
            df = pd.read_csv(
                file_map[ticker], usecols=["Date", "Close"],
                index_col="Date", parse_dates=True
            )
            all_close[ticker] = df["Close"]
    prices = pd.DataFrame(all_close).sort_index()
    return prices


# ============================================================
# MEMBERSHIP LOADING
# ============================================================

def load_membership(universe_folder):
    """Load SCD2 membership periods CSV. Cached per universe."""
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
    Pre-build {date -> [tickers]} for all rebalance dates in one pass.
    Much faster than checking membership per rebalance date individually.
    
    Args:
        universe_folder: Universe folder name
        rebal_dates: List of rebalance date timestamps
        
    Returns:
        Dict mapping each rebalance date to list of member tickers
    """
    df = load_membership(universe_folder)
    lookup = {}
    for date in rebal_dates:
        ts = pd.Timestamp(date)
        mask = (df["EntryDate"] <= ts) & ((df["ExitDate"].isna()) | (df["ExitDate"] > ts))
        lookup[date] = df.loc[mask, "Symbol"].tolist()
    return lookup
