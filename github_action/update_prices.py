"""
Download/update prices from multiple sources:
1. Twelve Data API (primary) — signal tickers + NASDAQ-100 + S&P 500
2. yfinance (secondary, batched) — remaining tickers (midcap, smallcap, russell)
Maintains a rolling parquet with ~400 days of data for all needed tickers.
"""

import pandas as pd
import yfinance as yf
import requests
import time
from datetime import datetime, timedelta
from pathlib import Path
from config import SIGNAL_TICKERS, UNIVERSES
from fetch_constituents import get_constituents
import os

DATA_DIR = Path(__file__).parent / "data"
PRICES_FILE = DATA_DIR / "prices.parquet"

TWELVE_DATA_KEY = os.environ.get("TWELVE_DATA_API_KEY", "")

# Tickers to pull from Twelve Data (critical ones)
TWELVE_DATA_UNIVERSES = ["nasdaq100", "sp500", "sp100", "djia"]


def get_all_tickers():
    """Get all distinct tickers needed (constituents + signals)."""
    all_tickers = set(SIGNAL_TICKERS)
    for config in UNIVERSES.values():
        source = config.get("constituents_source", "")
        members = get_constituents(source)
        all_tickers.update(members)
    clean = sorted([t for t in all_tickers if t and "-" not in t or t.startswith("^") or "=" in t])
    return clean


def get_twelve_data_tickers():
    """Get tickers for Twelve Data (signal + primary universes)."""
    tickers = set(SIGNAL_TICKERS)
    for universe in TWELVE_DATA_UNIVERSES:
        members = get_constituents(universe)
        tickers.update(members)
    # Twelve Data uses different format: ^NDX → NDX, GC=F → XAU/USD
    return sorted([t for t in tickers if "-" not in t])


def fetch_twelve_data(tickers, start_date, end_date):
    """Fetch daily close prices from Twelve Data API in batches of 8."""
    if not TWELVE_DATA_KEY:
        print("  ⚠️ No Twelve Data API key — skipping")
        return pd.DataFrame()
    
    all_data = {}
    # Twelve Data free tier: 8 symbols per batch request, 8 requests/min
    batch_size = 8
    
    # Map yfinance-style tickers to Twelve Data format
    ticker_map = {}
    for t in tickers:
        if t == "GC=F":
            ticker_map["XAU/USD"] = t
        elif t.startswith("^"):
            ticker_map[t[1:]] = t  # ^NDX → NDX
        else:
            ticker_map[t] = t
    
    td_tickers = list(ticker_map.keys())
    print(f"  Twelve Data: {len(td_tickers)} tickers in {len(td_tickers)//batch_size + 1} batches...")
    
    for i in range(0, len(td_tickers), batch_size):
        batch = td_tickers[i:i + batch_size]
        symbols = ",".join(batch)
        
        url = f"https://api.twelvedata.com/time_series?symbol={symbols}&interval=1day&start_date={start_date}&end_date={end_date}&outputsize=5000&apikey={TWELVE_DATA_KEY}"
        
        try:
            resp = requests.get(url, timeout=30)
            data = resp.json()
            
            if isinstance(data, dict) and "code" in data:
                print(f"    Error: {data.get('message', 'unknown')}")
                break
            
            # Single symbol returns differently than multiple
            if len(batch) == 1:
                data = {batch[0]: data}
            
            for td_symbol, series in data.items():
                if "values" not in series:
                    continue
                original_ticker = ticker_map.get(td_symbol, td_symbol)
                df = pd.DataFrame(series["values"])
                df["datetime"] = pd.to_datetime(df["datetime"])
                df = df.set_index("datetime").sort_index()
                all_data[original_ticker] = df["close"].astype(float)
            
        except Exception as e:
            print(f"    Batch error: {e}")
        
        # Rate limit: 8 requests/min
        if i + batch_size < len(td_tickers):
            time.sleep(8)  # conservative pause
    
    if all_data:
        result = pd.DataFrame(all_data).sort_index()
        print(f"  Twelve Data: got {result.shape[1]} tickers × {result.shape[0]} days")
        return result
    return pd.DataFrame()


def fetch_yfinance_batched(tickers, start_date, end_date, batch_size=500, pause=10):
    """Fetch prices from yfinance in batches with delays."""
    all_prices = pd.DataFrame()
    
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i + batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(tickers) - 1) // batch_size + 1
        print(f"    yfinance batch {batch_num}/{total_batches}: {len(batch)} tickers...", end=" ", flush=True)
        
        try:
            data = yf.download(batch, start=start_date, end=end_date, progress=False, auto_adjust=True, threads=True)
            if isinstance(data.columns, pd.MultiIndex):
                batch_prices = data["Close"]
            elif len(batch) == 1:
                batch_prices = data[["Close"]].rename(columns={"Close": batch[0]})
            else:
                batch_prices = data
            
            if all_prices.empty:
                all_prices = batch_prices
            else:
                all_prices = all_prices.join(batch_prices, how="outer")
            print(f"OK")
        except Exception as e:
            print(f"FAILED ({e})")
        
        if i + batch_size < len(tickers):
            time.sleep(pause)
    
    return all_prices


def update_prices():
    """Download/update price data from Twelve Data + yfinance."""
    today = pd.Timestamp(datetime.now().date())
    start = (today - timedelta(days=400)).strftime("%Y-%m-%d")
    end = (today + timedelta(days=1)).strftime("%Y-%m-%d")
    
    # Load existing or start fresh
    if PRICES_FILE.exists():
        prices = pd.read_parquet(PRICES_FILE)
        prices.index = pd.to_datetime(prices.index)
        last_date = prices.index[-1]
        days_missing = (today - last_date).days
        
        # Skip weekends — if last data is Friday and today is Sat/Sun, we're current
        if days_missing <= 2 and today.weekday() >= 5:  # Saturday=5, Sunday=6
            print(f"✅ Prices current (last: {last_date.date()}, weekend — no new data)")
            return prices
        
        if days_missing <= 0:
            print(f"✅ Prices current (last: {last_date.date()}, {prices.shape[1]} tickers)")
            return prices
        
        print(f"📥 Updating: {last_date.date()} → today ({days_missing} days)")
        start = (last_date + timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        print("📥 No cache — full download...")
        prices = pd.DataFrame()
    
    # Step 1: Twelve Data for critical tickers
    td_tickers = get_twelve_data_tickers()
    td_prices = fetch_twelve_data(td_tickers, start, end)
    
    # Step 2: yfinance for remaining tickers (batched)
    all_tickers = get_all_tickers()
    already_got = set(td_prices.columns) if not td_prices.empty else set()
    remaining = [t for t in all_tickers if t not in already_got]
    
    print(f"  yfinance: {len(remaining)} remaining tickers...")
    yf_prices = fetch_yfinance_batched(remaining, start, end)
    
    # Merge
    new_prices = td_prices
    if not yf_prices.empty:
        if new_prices.empty:
            new_prices = yf_prices
        else:
            new_prices = new_prices.join(yf_prices, how="outer")
    
    if new_prices.empty:
        print("  ⚠️ No new data")
        return prices if not prices.empty else pd.DataFrame()
    
    # Combine with existing
    if prices.empty:
        prices = new_prices
    else:
        combined = pd.concat([prices, new_prices]).sort_index()
        combined = combined[~combined.index.duplicated(keep="last")]
        prices = combined
    
    # Keep last 400 days
    if len(prices) > 400:
        prices = prices.iloc[-400:]
    
    # Save
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    prices.to_parquet(PRICES_FILE)
    print(f"✅ Saved: {prices.shape[0]} days × {prices.shape[1]} tickers ({PRICES_FILE.stat().st_size // 1024 // 1024} MB)")
    
    return prices


if __name__ == "__main__":
    update_prices()
