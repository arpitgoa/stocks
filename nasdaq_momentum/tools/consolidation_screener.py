#!/usr/bin/env python3
"""
Consolidation Breakout Screener (v3)
=====================================
Finds stocks making TINY candles relative to their recent average.

Detection logic:
  Candle size = (High - Low) / Close
  "Tight" = current candle < 45% of the average of prior 8 candles
  Pattern = 2+ consecutive tight candles after a big prior move

This adapts to each stock's own volatility — a 3% candle on STX is 
a squeeze, but 3% on MNST is normal.

Usage:
  python tools/consolidation_screener.py
  python tools/consolidation_screener.py -t weekly
  python tools/consolidation_screener.py -t daily
"""

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime
from pathlib import Path
import argparse

TIMEFRAME_CONFIG = {
    "monthly": {
        "move_window": 12,           # look for big move in last 12 months
        "prior_threshold": 0.40,     # 40%+ move somewhere in that window
        "squeeze_ratio": 0.50,       # candle < 50% of avg prior candles
        "avg_window": 6,             # avg over prior 6 months
        "min_tight": 2,              # 2+ tight candles in last 3 months
        "check_last_n": 3,           # check last 3 months for squeeze
        "resample": "ME",
        "label": "Monthly",
        "history": "3y",
    },
    "weekly": {
        "move_window": 26,           # big move in last 26 weeks (6 months)
        "prior_threshold": 0.25,     # 25%+ move
        "squeeze_ratio": 0.45,       # candle < 45% of avg prior candles
        "avg_window": 8,             # avg over prior 8 weeks
        "min_tight": 1,              # 1+ tight candle in last 3 weeks
        "check_last_n": 3,           # check last 3 weeks
        "resample": "W-FRI",
        "label": "Weekly",
        "history": "2y",
    },
    "daily": {
        "move_window": 60,           # big move in last 60 days (3 months)
        "prior_threshold": 0.15,     # 15%+ move
        "squeeze_ratio": 0.45,       # candle < 45% of avg
        "avg_window": 15,            # avg over prior 15 days
        "min_tight": 2,              # 2+ tight candles in last 5 days
        "check_last_n": 5,           # check last 5 days
        "resample": None,
        "label": "Daily",
        "history": "1y",
    },
}

SCAN_UNIVERSE = [
    "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "AVGO", "TSLA", "COST",
    "NFLX", "AMD", "ADBE", "CRM", "QCOM", "INTU", "AMAT", "ISRG", "BKNG", "MU",
    "LRCX", "KLAC", "SNPS", "CDNS", "PANW", "CRWD", "MRVL", "ORLY", "MNST", "NOW",
    "ASML", "ADI", "MELI", "WDAY", "REGN", "VRTX", "FTNT", "DASH", "TEAM", "TTD",
    "APP", "PLTR", "COIN", "SMCI", "ARM", "CEG", "UBER", "NET", "DDOG", "SHOP",
    "ROKU", "SNAP", "NIO", "SE", "ABNB", "HOOD", "MSTR", "RKLB",
    "SOFI", "AFRM", "UPST", "DUOL", "HIMS", "CAVA", "TOST",
    "INTC", "ON", "MCHP", "TXN", "NXPI", "SWKS", "STX", "WDC",
    "SNOW", "MDB", "VEEV", "ZS", "OKTA", "BILL",
    "ENPH", "SEDG", "FSLR", "JD", "BIDU", "PDD",
    "RIVN", "IONQ", "RGTI",
]


def download_ohlc(tickers, history="2y"):
    """Download OHLC data from yfinance."""
    print(f"  Downloading {len(tickers)} tickers ({history})...", end=" ", flush=True)
    try:
        data = yf.download(tickers, period=history, progress=False,
                           auto_adjust=True, threads=True)
        print(f"OK ({data.shape[0]} days)")
        return data
    except Exception as e:
        print(f"FAILED: {e}")
        return None


def get_ohlc_series(data, col):
    """Extract OHLC for a single ticker from multi-index DataFrame."""
    if isinstance(data.columns, pd.MultiIndex):
        h = data["High"][col].dropna()
        l = data["Low"][col].dropna()
        c = data["Close"][col].dropna()
        o = data["Open"][col].dropna()
    else:
        h = data["High"].dropna()
        l = data["Low"].dropna()
        c = data["Close"].dropna()
        o = data["Open"].dropna()
    # Align indices
    idx = h.index.intersection(l.index).intersection(c.index)
    return o.reindex(idx), h.reindex(idx), l.reindex(idx), c.reindex(idx)


def resample_series(o, h, l, c, rule):
    """Resample OHLC series."""
    if rule is None:
        return o, h, l, c
    o2 = o.resample(rule).first().dropna()
    h2 = h.resample(rule).max().dropna()
    l2 = l.resample(rule).min().dropna()
    c2 = c.resample(rule).last().dropna()
    idx = o2.index.intersection(h2.index).intersection(l2.index).intersection(c2.index)
    return o2.reindex(idx), h2.reindex(idx), l2.reindex(idx), c2.reindex(idx)


def scan_timeframe(data, config, tickers):
    """
    Find stocks with candle squeeze after a big move.
    
    New logic:
    1. Look at the last N candles (check_last_n) for any squeeze candles
    2. Look back further (move_window) for a big move at any point
    3. If both conditions met → flag it
    """
    resample = config["resample"]
    move_window = config["move_window"]
    prior_threshold = config["prior_threshold"]
    squeeze_ratio = config["squeeze_ratio"]
    avg_window = config["avg_window"]
    min_tight = config["min_tight"]
    check_last_n = config["check_last_n"]

    results = []

    for col in tickers:
        try:
            o, h, l, c = get_ohlc_series(data, col)
        except (KeyError, TypeError):
            continue

        o, h, l, c = resample_series(o, h, l, c, resample)

        if len(c) < move_window + avg_window + 5:
            continue

        # Candle size as % of close
        candle_pct = (h - l) / c

        # Rolling average of candle size (prior N periods, shifted)
        avg_candle = candle_pct.rolling(avg_window).mean().shift(1)

        # Ratio: current candle / rolling avg
        ratio = candle_pct / avg_candle

        # Check last N candles for squeeze
        recent_ratios = ratio.iloc[-check_last_n:]
        tight_candles = (recent_ratios < squeeze_ratio).sum()

        if tight_candles < min_tight:
            continue

        # Find biggest move in the move_window before the squeeze
        # Max peak-to-current or trough-to-peak in that window
        lookback_start = max(0, len(c) - move_window - check_last_n)
        lookback_end = len(c) - check_last_n  # up to where squeeze starts
        
        if lookback_end - lookback_start < 5:
            continue

        window_prices = c.iloc[lookback_start:lookback_end]
        # Find the max run-up: from any low to any subsequent high
        window_low = window_prices.min()
        # Get index of low, then find max after it
        low_idx = window_prices.idxmin()
        after_low = window_prices.loc[low_idx:]
        if len(after_low) < 2:
            continue
        window_high = after_low.max()
        
        if window_low <= 0:
            continue
        max_move = window_high / window_low - 1

        if max_move < prior_threshold:
            continue

        # Stats
        current_price = c.iloc[-1]
        # Find the squeeze candles specifically
        squeeze_idx = [i for i in range(-check_last_n, 0) 
                       if ratio.iloc[i] < squeeze_ratio]
        avg_tight = candle_pct.iloc[squeeze_idx].mean() * 100 if squeeze_idx else 0
        prior_avg = avg_candle.iloc[-1] * 100 if pd.notna(avg_candle.iloc[-1]) else 0
        best_ratio = recent_ratios.min()
        
        # Distance from recent high
        recent_high = h.iloc[-check_last_n:].max()
        dist_high = (current_price / recent_high - 1) * 100

        results.append({
            "ticker": col,
            "prior_move": max_move * 100,
            "tight_candles": int(tight_candles),
            "squeeze_candle": avg_tight,
            "normal_candle": prior_avg,
            "best_ratio": best_ratio,
            "price": current_price,
            "dist_high": dist_high,
            "near_breakout": dist_high > -3.0,
        })

    return pd.DataFrame(results)


def print_results(df, label, config):
    """Print screener output."""
    if df.empty:
        print(f"\n  No stocks found for {label}.\n")
        return

    df = df.sort_values(["near_breakout", "best_ratio"],
                        ascending=[False, True])

    sep = "=" * 95
    print(f"\n{sep}")
    print(f"  {label.upper()} — Candle Squeeze After Big Move")
    print(f"  Candle < {config['squeeze_ratio']*100:.0f}% of avg | "
          f"Prior move > {config['prior_threshold']*100:.0f}% in last "
          f"{config['move_window']} periods")
    print(f"{sep}\n")

    near = df[df["near_breakout"]]
    far = df[~df["near_breakout"]]

    hdr = (f"  {'Ticker':<7} {'BigMove':<9} {'#Tight':<7} "
           f"{'Candle':<8} {'Normal':<8} {'Ratio':<7} {'Price':<10} {'vs Hi'}")
    div = f"  {'-'*75}"

    if not near.empty:
        print("  🔥 NEAR BREAKOUT (within 3% of high):")
        print(hdr)
        print(div)
        for _, r in near.iterrows():
            print(f"  {r['ticker']:<7} +{r['prior_move']:.0f}%    "
                  f"{r['tight_candles']:<7} "
                  f"{r['squeeze_candle']:.1f}%   "
                  f"{r['normal_candle']:.1f}%   "
                  f"{r['best_ratio']:.2f}   "
                  f"${r['price']:<8.2f} {r['dist_high']:+.1f}%")
        print()

    if not far.empty:
        print("  📊 SQUEEZED (below high):")
        print(hdr)
        print(div)
        for _, r in far.iterrows():
            print(f"  {r['ticker']:<7} +{r['prior_move']:.0f}%    "
                  f"{r['tight_candles']:<7} "
                  f"{r['squeeze_candle']:.1f}%   "
                  f"{r['normal_candle']:.1f}%   "
                  f"{r['best_ratio']:.2f}   "
                  f"${r['price']:<8.2f} {r['dist_high']:+.1f}%")
        print()

    print(f"  Total: {len(df)} | Near breakout: {len(near)} "
          f"| Squeezed: {len(far)}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Consolidation Screener — Candle Squeeze Detection")
    parser.add_argument("--timeframe", "-t",
                        choices=["monthly", "weekly", "daily", "all"],
                        default="all")
    args = parser.parse_args()

    timeframes = (["monthly", "weekly", "daily"]
                  if args.timeframe == "all" else [args.timeframe])
    tickers = sorted(set(SCAN_UNIVERSE))

    hist_map = {"monthly": "3y", "weekly": "2y", "daily": "1y"}
    max_hist = max(hist_map[tf] for tf in timeframes)

    print(f"\n{'='*60}")
    print(f"  CONSOLIDATION SCREENER (Candle Squeeze)")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}")
    print(f"  Universe: {len(tickers)} stocks")
    print(f"  Timeframes: {', '.join(timeframes)}\n")

    data = download_ohlc(tickers, max_hist)
    if data is None:
        return

    # Figure out which tickers are available
    if isinstance(data.columns, pd.MultiIndex):
        available = [t for t in tickers if t in data["Close"].columns]
    else:
        available = tickers[:1]

    for tf in timeframes:
        config = TIMEFRAME_CONFIG[tf]
        print(f"\n  Scanning {config['label']}...")
        results = scan_timeframe(data, config, available)
        print_results(results, config["label"], config)


if __name__ == "__main__":
    main()
