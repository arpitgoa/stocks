"""
Download/update prices from yfinance.
Maintains a rolling parquet with ~400 days of data for all needed tickers.
Incremental: only downloads missing days.
"""

import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from pathlib import Path
from config import SIGNAL_TICKERS, UNIVERSES
from fetch_constituents import get_constituents

DATA_DIR = Path(__file__).parent / "data"
PRICES_FILE = DATA_DIR / "prices.parquet"


def get_all_tickers():
    """Get all distinct tickers needed (constituents + signals)."""
    all_tickers = set(SIGNAL_TICKERS)
    
    for config in UNIVERSES.values():
        source = config.get("constituents_source", "")
        members = get_constituents(source)
        all_tickers.update(members)
    
    # Filter out invalid tickers
    clean = sorted([t for t in all_tickers if t and "-" not in t or t.startswith("^") or "=" in t])
    return clean


def update_prices():
    """Download/update price data. Incremental if parquet exists."""
    today = pd.Timestamp(datetime.now().date())
    
    # Load existing or start fresh
    if PRICES_FILE.exists():
        prices = pd.read_parquet(PRICES_FILE)
        prices.index = pd.to_datetime(prices.index)
        last_date = prices.index[-1]
        days_missing = (today - last_date).days
        
        if days_missing <= 0:
            print(f"✅ Prices current (last: {last_date.date()}, {prices.shape[1]} tickers)")
            return prices
        
        print(f"📥 Updating prices: {last_date.date()} → today ({days_missing} days missing)")
        all_tickers = get_all_tickers()
        # Only download tickers that exist in our parquet + new ones
        download_tickers = list(set(all_tickers) | set(prices.columns))
        
        start = (last_date + timedelta(days=1)).strftime("%Y-%m-%d")
        end = (today + timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        print("📥 No price cache — downloading full 400 days...")
        all_tickers = get_all_tickers()
        download_tickers = all_tickers
        start = (today - timedelta(days=400)).strftime("%Y-%m-%d")
        end = (today + timedelta(days=1)).strftime("%Y-%m-%d")
        prices = pd.DataFrame()
    
    print(f"  Downloading {len(download_tickers)} tickers...")
    
    try:
        data = yf.download(
            download_tickers, start=start, end=end,
            progress=False, auto_adjust=True, threads=True
        )
        
        if isinstance(data.columns, pd.MultiIndex):
            new_prices = data["Close"]
        else:
            new_prices = data
        
        if new_prices.empty:
            print("  No new data available")
            return prices if not prices.empty else pd.DataFrame()
        
        if prices.empty:
            prices = new_prices
        else:
            # Append new dates
            combined = pd.concat([prices, new_prices]).sort_index()
            combined = combined[~combined.index.duplicated(keep="last")]
            prices = combined
        
        # Keep only last 400 trading days to manage file size
        if len(prices) > 400:
            prices = prices.iloc[-400:]
        
        # Save
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        prices.to_parquet(PRICES_FILE)
        print(f"✅ Saved: {prices.shape[0]} days × {prices.shape[1]} tickers ({PRICES_FILE.stat().st_size // 1024 // 1024} MB)")
        
    except Exception as e:
        print(f"❌ Download failed: {e}")
    
    return prices


if __name__ == "__main__":
    update_prices()
