"""
Fetch current index constituents from multiple public sources.
Uses fallback chain: Wikipedia → ETF holdings page → cached CSV.
Saves ticker lists to data/constituents/{index_name}.csv
"""

import pandas as pd
import requests
from io import StringIO
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data" / "constituents"
DATA_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


# ============================================================
# SOURCE: Wikipedia
# ============================================================

def fetch_sp500_wikipedia():
    """S&P 500 from Wikipedia — most reliable."""
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    tables = pd.read_html(StringIO(resp.text))
    df = tables[0]
    if "Symbol" in df.columns:
        return df["Symbol"].str.replace(".", "-", regex=False).tolist()
    return []


def fetch_sp100_wikipedia():
    """S&P 100 from Wikipedia."""
    url = "https://en.wikipedia.org/wiki/S%26P_100"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    tables = pd.read_html(StringIO(resp.text))
    # Find table with 'Symbol' column and ~100 rows
    for t in tables:
        if "Symbol" in t.columns and len(t) > 80:
            return t["Symbol"].str.replace(".", "-", regex=False).tolist()
    return []


def fetch_djia_wikipedia():
    """DJIA from Wikipedia."""
    url = "https://en.wikipedia.org/wiki/Dow_Jones_Industrial_Average"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    tables = pd.read_html(StringIO(resp.text))
    for t in tables:
        if "Symbol" in t.columns and 25 <= len(t) <= 35:
            return t["Symbol"].str.replace(".", "-", regex=False).tolist()
        if "Ticker" in t.columns and 25 <= len(t) <= 35:
            return t["Ticker"].str.replace(".", "-", regex=False).tolist()
    return []


def fetch_nasdaq100_wikipedia():
    """NASDAQ-100 — try the dedicated components page."""
    # Try the slickcharts source (more reliable than Wikipedia for NDX)
    try:
        url = "https://www.slickcharts.com/nasdaq100"
        resp = requests.get(url, headers=HEADERS, timeout=30)
        tables = pd.read_html(StringIO(resp.text))
        for t in tables:
            if "Symbol" in t.columns and len(t) > 90:
                return t["Symbol"].str.strip().tolist()
    except:
        pass
    
    # Fallback: hardcoded FMP-style API (free)
    try:
        url = "https://financialmodelingprep.com/api/v3/nasdaq_constituent?apikey=demo"
        resp = requests.get(url, headers=HEADERS, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list) and len(data) > 50:
                return [item["symbol"] for item in data if "symbol" in item]
    except:
        pass
    
    return []


# ============================================================
# SOURCE: ETF Holdings (iShares/SPDR)
# ============================================================

def fetch_ishares_etf(etf_ticker, product_id):
    """Fetch holdings from iShares (BlackRock) CSV download."""
    url = f"https://www.ishares.com/us/products/{product_id}/ishares-{etf_ticker.lower()}-etf/1467271812596.ajax?fileType=csv&fileName={etf_ticker}_holdings&dataType=fund"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        if resp.status_code != 200:
            return []
        
        lines = resp.text.split('\n')
        # Find header row
        for i, line in enumerate(lines):
            if 'Ticker' in line and 'Name' in line:
                csv_text = '\n'.join(lines[i:])
                df = pd.read_csv(StringIO(csv_text), on_bad_lines='skip')
                if 'Ticker' in df.columns:
                    tickers = df['Ticker'].dropna().astype(str).str.strip()
                    tickers = [t for t in tickers if t and t != '-' and len(t) <= 6 and not t.startswith('--')]
                    return tickers
                break
    except Exception as e:
        print(f"    iShares error: {e}")
    return []


def fetch_spdr_etf(etf_ticker):
    """Fetch holdings from SPDR (State Street) — for MDY."""
    url = f"https://www.ssga.com/us/en/intermediary/etfs/library-content/products/fund-data/etfs/us/holdings-daily-us-en-{etf_ticker.lower()}.xlsx"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        if resp.status_code == 200:
            df = pd.read_excel(StringIO(resp.content.decode('latin-1')), skiprows=4)
            if 'Ticker' in df.columns:
                return df['Ticker'].dropna().astype(str).str.strip().tolist()
    except:
        pass
    return []


# ============================================================
# MAIN FETCH LOGIC
# ============================================================

FETCH_FUNCTIONS = {
    "nasdaq100": [fetch_nasdaq100_wikipedia],
    "sp500": [fetch_sp500_wikipedia],
    "sp100": [fetch_sp100_wikipedia],
    "djia": [fetch_djia_wikipedia],
    "sp_midcap400": [lambda: fetch_ishares_etf("MDY", "239726")],
    "sp_smallcap600": [lambda: fetch_ishares_etf("IJR", "239774")],
    "russell1000": [lambda: fetch_ishares_etf("IWB", "239707")],
    "russell2000": [lambda: fetch_ishares_etf("IWM", "239710")],
}


def fetch_all():
    """Fetch constituents for all indices. Uses fallback chain."""
    results = {}
    
    for index_name, fetch_funcs in FETCH_FUNCTIONS.items():
        print(f"Fetching {index_name}...", end=" ")
        tickers = []
        
        for func in fetch_funcs:
            try:
                tickers = func()
                if tickers and len(tickers) > 10:
                    break
            except Exception as e:
                print(f"({e})", end=" ")
                continue
        
        if tickers and len(tickers) > 10:
            output_file = DATA_DIR / f"{index_name}.csv"
            pd.DataFrame({"Symbol": sorted(tickers)}).to_csv(output_file, index=False)
            results[index_name] = {"tickers": tickers, "source": "live"}
            print(f"✅ {len(tickers)} tickers")
        else:
            # Fall back to cached file
            cached = DATA_DIR / f"{index_name}.csv"
            if cached.exists():
                df = pd.read_csv(cached)
                results[index_name] = {"tickers": df["Symbol"].tolist(), "source": "cached"}
                print(f"⚠️ Using cached ({len(results[index_name]['tickers'])} tickers)")
            else:
                print(f"❌ No data")
    
    return results


def get_constituents(index_name):
    """Get current constituents for an index (from cached CSV)."""
    csv_path = DATA_DIR / f"{index_name}.csv"
    if csv_path.exists():
        return pd.read_csv(csv_path)["Symbol"].tolist()
    return []


if __name__ == "__main__":
    results = fetch_all()
    print(f"\nTotal indices: {len(results)}")
    total = set()
    for tickers in results.values():
        total.update(tickers)
    print(f"Total distinct tickers: {len(total)}")
