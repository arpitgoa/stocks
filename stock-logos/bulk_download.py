#!/usr/bin/env python3
"""
bulk_download.py — Download stock logos from Logo.dev and cache them locally.

Usage:
    python bulk_download.py                    # Download all tickers from tickers.txt
    python bulk_download.py --tickers AAPL,TSLA,NVDA   # Download specific tickers
    python bulk_download.py --file tickers.txt          # One ticker per line
    python bulk_download.py --force                     # Re-download even if cached

Downloads 26 tickers in parallel (one per letter bucket A-Z), then moves to
the next batch. This keeps concurrency bounded and avoids rate limiting.

Logos are saved to ./logos/<TICKER>.png
"""

import os
import string
import argparse
import urllib.request
import urllib.error
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

LOGO_DEV_TOKEN = "pk_YWcpl2HqTTyigO9G_HrRWA"
LOGOS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logos")
SIZE = 800  # Max quality from Logo.dev (retina=true gives 1600px actual)

# Default hardcoded universe (fallback if tickers.txt doesn't exist)
DEFAULT_UNIVERSE = [
    "SPY", "QQQ", "IWM", "DIA", "VOO", "AAPL", "MSFT", "GOOGL", "AMZN",
    "NVDA", "META", "TSLA", "JPM", "V", "JNJ", "WMT", "PG", "MA", "UNH",
    "HD", "DIS", "BAC", "XOM", "PFE", "ABBV", "KO", "PEP", "AVGO", "COST",
    "AMD", "CRM", "ADBE", "NFLX", "PYPL", "INTC", "QCOM", "PLTR", "COIN",
]


def download_logo(ticker: str, force: bool = False) -> tuple[str, bool, str]:
    """Download a single ticker logo. Returns (ticker, success, message)."""
    filepath = os.path.join(LOGOS_DIR, f"{ticker}.png")

    if os.path.exists(filepath) and not force:
        return (ticker, True, "cached")

    url = (
        f"https://img.logo.dev/ticker/{ticker}"
        f"?token={LOGO_DEV_TOKEN}&size={SIZE}&format=png&retina=true&theme=dark&fallback=404"
    )

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "StockLogoCache/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status == 200:
                data = resp.read()
                with open(filepath, "wb") as f:
                    f.write(data)
                size_kb = len(data) / 1024
                return (ticker, True, f"{size_kb:.1f} KB")
            else:
                return (ticker, False, f"HTTP {resp.status}")
    except urllib.error.HTTPError as e:
        return (ticker, False, f"HTTP {e.code}")
    except Exception as e:
        return (ticker, False, str(e))


def main():
    parser = argparse.ArgumentParser(description="Download stock logos from Logo.dev")
    parser.add_argument("--tickers", type=str, help="Comma-separated tickers")
    parser.add_argument("--file", type=str, help="File with one ticker per line")
    parser.add_argument("--force", action="store_true", help="Re-download even if cached")
    args = parser.parse_args()

    # Determine ticker list
    if args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    elif args.file:
        with open(args.file) as f:
            tickers = [line.strip().upper() for line in f if line.strip()]
    else:
        default_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tickers.txt")
        if os.path.exists(default_file):
            with open(default_file) as f:
                tickers = [line.strip().upper() for line in f if line.strip()]
        else:
            tickers = DEFAULT_UNIVERSE

    os.makedirs(LOGOS_DIR, exist_ok=True)

    # Group tickers by first letter (A-Z + other)
    buckets = defaultdict(list)
    for t in tickers:
        key = t[0].upper() if t and t[0].isalpha() else '#'
        buckets[key].append(t)

    print(f"Downloading logos for {len(tickers)} tickers across {len(buckets)} letter buckets")
    print(f"Strategy: 26 parallel downloads (one per letter bucket per round)")
    print(f"Output: {LOGOS_DIR}/")
    print()

    success = 0
    skipped = 0
    failed = 0

    # Find the max bucket size (number of rounds needed)
    max_bucket_size = max(len(v) for v in buckets.values())
    letters = sorted(buckets.keys())

    for round_idx in range(max_bucket_size):
        # Pick one ticker from each letter bucket for this round
        batch = []
        for letter in letters:
            if round_idx < len(buckets[letter]):
                batch.append(buckets[letter][round_idx])

        if not batch:
            break

        # Download batch of up to 26 in parallel
        with ThreadPoolExecutor(max_workers=26) as executor:
            futures = {
                executor.submit(download_logo, ticker, args.force): ticker
                for ticker in batch
            }
            for future in as_completed(futures):
                ticker, ok, msg = future.result()
                if msg == "cached":
                    skipped += 1
                elif ok:
                    success += 1
                    print(f"  ✓ {ticker} ({msg})")
                else:
                    failed += 1
                    if "404" not in msg:
                        print(f"  ✗ {ticker} — {msg}")

        # Progress update every round
        done = success + skipped + failed
        if (round_idx + 1) % 10 == 0:
            print(f"  ... round {round_idx + 1}/{max_bucket_size} — {done}/{len(tickers)} processed")

    print()
    print(f"Done: {success} downloaded, {skipped} already cached, {failed} failed/no-logo")
    print(f"Total logos in cache: {len([f for f in os.listdir(LOGOS_DIR) if f.endswith('.png')])}")


if __name__ == "__main__":
    main()
