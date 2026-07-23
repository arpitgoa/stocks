#!/usr/bin/env python3
"""
Live Signal Generator — All Universes
=======================================
Pulls live prices from yfinance (with local caching to avoid repeated downloads),
calculates momentum scores, applies buffer logic, and outputs trading signals.

Usage:
    python live_signal.py                           # All universes
    python live_signal.py --universe nasdaq100_vix  # Single universe
    python live_signal.py --universe nasdaq100_vix --holdings NVDA,AVGO,APP
    python live_signal.py --refresh                 # Force re-download all data

Requirements:
    pip install yfinance pandas numpy
"""

import argparse
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from pathlib import Path

from universe_config import UNIVERSE_CONFIGS, get_config
from leveraged_config import LEVERAGED_ETF_MAP

# ============================================================
# PATHS & CONFIG
# ============================================================

# Single source of truth for all price data — shared with backtest & dashboards
PRICES_PARQUET = Path(__file__).parent / "data" / "all_prices.parquet"

# ============================================================
# YFINANCE TICKER MAPPING
# ============================================================

# Map Norgate index symbols to yfinance tickers
INDEX_YFINANCE_MAP = {
    "$NDX": "^NDX",
    "$SPX": "^GSPC",
    "$OEX": "^OEX",
    "$MID": "^MID",
    "$SML": "^SML",
    "$RUI": "^RUI",
    "$RUT": "^RUT",
    "$RMC": "^RMC",
    "$RT200": "^RT200",
    "$DJI": "^DJI",
    "$NBI": "^NBI",
    "$NXTQ": "^NXTQ",
    "$VIX": "^VIX",
    "XAUUSD": "GC=F",
}

# Reverse map: yfinance ticker → Norgate name (for parquet column naming)
YFINANCE_TO_NORGATE = {v: k for k, v in INDEX_YFINANCE_MAP.items()}

# Universes where yfinance may not have the gold signal index
# Use NDX as fallback for ratio calculation
FALLBACK_GOLD_INDEX = {
    "$RMC": "^RUI",      # Russell Mid Cap → use Russell 1000 as proxy
    "$RT200": "^GSPC",   # Russell Top 200 → use S&P 500 as proxy
    "$NXTQ": "^NDX",     # NASDAQ Q-50 → use NDX
    "$SML": "^GSPC",     # S&P SmallCap 600 → use S&P 500 as proxy
}

# ============================================================
# DATA LOADING (with local cache + incremental updates)
# ============================================================

UNIVERSES_DIR = Path.home() / "Documents" / "workspace" / "historical-index-universe-data" / "universes"


def get_current_members(universe_folder):
    """Get current index members from SCD2 membership file."""
    csv_path = UNIVERSES_DIR / universe_folder / "membership_periods.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"Membership file not found: {csv_path}")
    df = pd.read_csv(csv_path)
    current = df[df["ExitDate"].isna()]
    return current["Symbol"].tolist()


def get_all_tickers_needed():
    """
    Get ALL distinct current constituent tickers across all universes + signal tickers.
    Only current members (ExitDate is null) — no historical/delisted stocks.
    Returns one flat list for a single yfinance call.
    """
    all_tickers = set()
    for name, config in UNIVERSE_CONFIGS.items():
        try:
            members = get_current_members(config["folder"])
            all_tickers.update(members)
        except FileNotFoundError:
            continue
    
    # Add signal tickers (yfinance format)
    for yf_ticker in INDEX_YFINANCE_MAP.values():
        if yf_ticker:
            all_tickers.add(yf_ticker)
    for yf_ticker in FALLBACK_GOLD_INDEX.values():
        if yf_ticker:
            all_tickers.add(yf_ticker)
    
    # Add benchmark ETFs
    for config in UNIVERSE_CONFIGS.values():
        etf = config.get("benchmark_etf", "")
        if etf:
            all_tickers.add(etf)
    
    # Filter: only valid yfinance tickers (no Norgate date-suffixed delisted symbols)
    clean = sorted([t for t in all_tickers if "-" not in t])
    return clean


def _rename_yfinance_to_norgate(df):
    """Rename yfinance signal columns to Norgate names so backtest engine can find them."""
    rename_map = {yf_name: norgate_name 
                  for yf_name, norgate_name in YFINANCE_TO_NORGATE.items() 
                  if yf_name in df.columns}
    if rename_map:
        df = df.rename(columns=rename_map)
    return df


def load_cached_prices():
    """Load the main prices parquet (shared with backtest & dashboard)."""
    if PRICES_PARQUET.exists():
        df = pd.read_parquet(PRICES_PARQUET)
        df.index = pd.to_datetime(df.index)
        return df
    return None


def save_prices(df):
    """Save to the main parquet file (shared with backtest & dashboard)."""
    PRICES_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(PRICES_PARQUET)


def update_prices(force_refresh=False):
    """
    Load existing parquet and append only missing days from yfinance.
    Downloads ALL tickers in a single yfinance call (no batching/looping).
    
    The parquet at data/all_prices.parquet is the single source of truth
    shared by: live_signal.py, run_backtest.py, generate_dashboard.py
    """
    today = pd.Timestamp(datetime.now().date())
    cached = load_cached_prices()
    
    if cached is not None and not force_refresh:
        last_date = cached.index[-1]
        days_missing = (today - last_date).days
        
        if days_missing <= 0:
            print(f"  ✅ Prices current (last: {last_date.date()}, {cached.shape[1]} tickers)")
            return cached
        
        # Skip download on weekends (no new trading data expected)
        weekday = today.weekday()  # 0=Mon, 5=Sat, 6=Sun
        if weekday == 6:  # Sunday
            # Data through Friday is sufficient
            if days_missing <= 2:
                print(f"  ✅ Weekend (Sun) — data through {last_date.date()} is current. Skipping download.")
                return cached
        elif weekday == 5:  # Saturday
            if days_missing <= 1:
                print(f"  ✅ Weekend (Sat) — data through {last_date.date()} is current. Skipping download.")
                return cached
        
        # Skip if last data is from today or the most recent trading day
        # (Mon morning before market open: last Friday's data is fine)
        if weekday == 0 and days_missing <= 3:
            # Monday: Friday data (3 days ago at most) is fine before market close
            from datetime import time as dtime
            now_time = datetime.now().time()
            if now_time < dtime(16, 30):  # Before 4:30 PM (market close + buffer)
                # Check if last_date is the previous Friday
                if last_date.weekday() == 4:  # Friday
                    print(f"  ✅ Monday pre-market — data through {last_date.date()} (Fri) is current. Skipping download.")
                    return cached
        
        # Incremental: one single call for all current constituents + signals
        print(f"  📥 Last data: {last_date.date()} → downloading {days_missing} missing day(s)...")
        live_tickers = get_all_tickers_needed()  # distinct current members + signals
        print(f"  {len(live_tickers)} tickers (current constituents only)...")
        start = (last_date + timedelta(days=1)).strftime("%Y-%m-%d")
        end = (today + timedelta(days=1)).strftime("%Y-%m-%d")
        
        try:
            new_data = yf.download(
                live_tickers, start=start, end=end,
                progress=False, auto_adjust=True, threads=True
            )
            if isinstance(new_data.columns, pd.MultiIndex):
                new_prices = new_data["Close"]
            else:
                new_prices = new_data
            
            if len(new_prices) > 0:
                new_prices = _rename_yfinance_to_norgate(new_prices)
                combined = pd.concat([cached, new_prices]).sort_index()
                combined = combined[~combined.index.duplicated(keep="last")]
                save_prices(combined)
                print(f"  ✅ Updated: +{len(new_prices)} day(s) → now through {combined.index[-1].date()}")
                return combined
            else:
                print(f"  ✅ No new trading days yet")
                return cached
        except Exception as e:
            print(f"  ⚠️ Update failed ({e}), using existing data")
            return cached
    
    # Full download — only for tickers NOT already in the existing parquet
    if force_refresh:
        print("  🔄 Force refresh — downloading latest prices for current members...")
    else:
        print("  📥 No parquet found — need Norgate data or a full download...")
        print("  ⚠️  Run 'python scripts/build_prices_parquet.py' first for historical data.")
        print("      Or use --refresh to download ~400 days from yfinance (limited history).")
        return cached if cached is not None else pd.DataFrame()
    
    all_tickers = get_all_tickers_needed()
    print(f"  {len(all_tickers)} tickers (current constituents + signals), 400 days, single call...")
    
    end = (today + timedelta(days=1)).strftime("%Y-%m-%d")
    start = (today - timedelta(days=400)).strftime("%Y-%m-%d")
    
    data = yf.download(
        all_tickers, start=start, end=end,
        progress=True, auto_adjust=True, threads=True
    )
    
    if isinstance(data.columns, pd.MultiIndex):
        all_prices = data["Close"]
    else:
        all_prices = data
    
    if not all_prices.empty:
        all_prices.sort_index(inplace=True)
        all_prices = _rename_yfinance_to_norgate(all_prices)
        
        # If existing parquet has historical data, merge with it
        if cached is not None:
            # Keep historical data, add/update with fresh yfinance data
            # Only update columns that exist in the download
            for col in all_prices.columns:
                if col in cached.columns:
                    # Append new dates only
                    new_dates = all_prices.index.difference(cached.index)
                    if len(new_dates) > 0:
                        cached.loc[new_dates, col] = all_prices.loc[new_dates, col]
                else:
                    cached[col] = all_prices[col]
            cached.sort_index(inplace=True)
            save_prices(cached)
            print(f"  ✅ Merged with historical: {cached.shape[0]} days × {cached.shape[1]} tickers")
            return cached
        else:
            save_prices(all_prices)
            print(f"  ✅ Saved: {all_prices.shape[0]} days × {all_prices.shape[1]} tickers")
            return all_prices
    
    return cached


def get_signal_prices():
    """Get VIX, gold, and index prices from the main parquet."""
    cached = load_cached_prices()
    if cached is not None:
        # Try both Norgate names ($NDX) and yfinance names (^NDX)
        signal_cols = {}
        for norgate_name, yf_name in INDEX_YFINANCE_MAP.items():
            if norgate_name in cached.columns:
                signal_cols[yf_name] = cached[norgate_name].tail(5)
            elif yf_name and yf_name in cached.columns:
                signal_cols[yf_name] = cached[yf_name].tail(5)
        
        if signal_cols:
            return pd.DataFrame(signal_cols)
    
    # Fallback: direct download
    signal_tickers = [v for v in INDEX_YFINANCE_MAP.values() if v]
    print("  ⚠️ Signal data not in cache — downloading directly...")
    data = yf.download(signal_tickers, period="5d", progress=False, auto_adjust=True)
    if isinstance(data.columns, pd.MultiIndex):
        return data["Close"]
    return data


# ============================================================
# MOMENTUM SCORING
# ============================================================

def calculate_scores(prices, tickers, lookback_long=252, lookback_short=126, skip_days=5,
                     weight_12=0.7, weight_6=0.3):
    """Calculate momentum scores for given tickers."""
    results = []
    
    for ticker in tickers:
        if ticker not in prices.columns:
            continue
        ts = prices[ticker].dropna()
        if len(ts) < lookback_long + skip_days + 10:
            continue
        
        end_idx = len(ts) - 1 - skip_days
        if end_idx < lookback_long:
            continue
        
        price_end = ts.iloc[end_idx]
        price_long = ts.iloc[end_idx - lookback_long]
        price_short = ts.iloc[end_idx - lookback_short]
        
        if price_long <= 0 or price_short <= 0:
            continue
        
        # Volatility
        log_rets = np.log(
            ts.iloc[end_idx - lookback_long:end_idx + 1] /
            ts.iloc[end_idx - lookback_long:end_idx + 1].shift(1)
        ).dropna()
        if len(log_rets) < 100:
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
    df["Weighted_Z"] = weight_12 * df["Z_12"] + weight_6 * df["Z_6"]
    df["Momentum_Score"] = df["Weighted_Z"].apply(
        lambda z: (1 + z) if z >= 0 else 1 / (1 - z)
    )
    df["Rank"] = df["Momentum_Score"].rank(ascending=False).astype(int)
    return df.sort_values("Momentum_Score", ascending=False).reset_index(drop=True)


# ============================================================
# SIGNAL GENERATION
# ============================================================

def generate_signal(universe_name, current_holdings=None):
    """Generate trading signal for a universe."""
    config = get_config(universe_name)
    universe_folder = config["folder"]
    top_n = config["top_n"]
    entry_rank = config["entry_rank"]
    exit_rank = config["exit_rank"]
    gold_threshold = config["gold_threshold"]
    gold_signal_index = config.get("gold_signal_index", "$NDX")
    vix_threshold = config.get("vix_threshold", None)
    vix_fast_long = config.get("vix_fast_long", 126)
    vix_fast_short = config.get("vix_fast_short", 42)
    
    if current_holdings is None:
        current_holdings = set()
    else:
        current_holdings = set(current_holdings)
    
    # Get current members
    members = get_current_members(universe_folder)
    print(f"  Universe: {config['label']} ({len(members)} current members)")
    
    # Get prices from cache
    cached = load_cached_prices()
    if cached is None:
        raise RuntimeError("No price cache. Run with --refresh first.")
    
    available = [t for t in members if t in cached.columns]
    prices = cached[available]
    print(f"  Prices available: {len(available)}/{len(members)}")
    
    # Get signal data from cache
    signal_data = get_signal_prices()
    
    # Check gold signal
    yf_gold_idx = INDEX_YFINANCE_MAP.get(gold_signal_index)
    if yf_gold_idx is None or yf_gold_idx not in signal_data.columns:
        yf_gold_idx = FALLBACK_GOLD_INDEX.get(gold_signal_index)
    
    gold_series = signal_data["GC=F"].dropna() if "GC=F" in signal_data.columns else pd.Series(dtype=float)
    gold_price = gold_series.iloc[-1] if len(gold_series) > 0 else None
    index_series = signal_data[yf_gold_idx].dropna() if yf_gold_idx and yf_gold_idx in signal_data.columns else pd.Series(dtype=float)
    index_price = index_series.iloc[-1] if len(index_series) > 0 else None
    vix_series = signal_data["^VIX"].dropna() if "^VIX" in signal_data.columns else pd.Series(dtype=float)
    vix_value = vix_series.iloc[-1] if len(vix_series) > 0 else None
    
    gold_ratio = index_price / gold_price if (index_price and gold_price and gold_price > 0) else None
    
    # Gold rotation check
    go_gold = False
    if gold_ratio is not None and gold_ratio >= gold_threshold:
        go_gold = True
    
    # VIX check
    use_fast_lookback = False
    if vix_threshold and vix_value and vix_value > vix_threshold:
        use_fast_lookback = True
    
    # Calculate scores
    if use_fast_lookback:
        lookback_long, lookback_short = vix_fast_long, vix_fast_short
        w12, w6 = 0.5, 0.5  # More responsive blend in panic
    else:
        lookback_long, lookback_short = 252, 126
        w12, w6 = 0.7, 0.3  # Favor sustained trend in calm markets
    
    scores = calculate_scores(prices, available, lookback_long, lookback_short,
                              weight_12=w12, weight_6=w6)
    
    # Apply buffer logic
    new_portfolio = set()
    if not scores.empty and not go_gold:
        ranked = dict(zip(scores["Ticker"], scores["Rank"]))
        
        # Retain existing holdings within exit rank
        retained = {t for t in current_holdings if t in ranked and ranked[t] <= exit_rank}
        new_portfolio = retained.copy()
        
        # Fill from top ranked within entry rank
        for _, row in scores.iterrows():
            if len(new_portfolio) >= top_n:
                break
            if row["Ticker"] not in new_portfolio and row["Rank"] <= entry_rank:
                new_portfolio.add(row["Ticker"])
        
        # Fill remaining from best available
        if len(new_portfolio) < top_n:
            for _, row in scores.iterrows():
                if len(new_portfolio) >= top_n:
                    break
                if row["Ticker"] not in new_portfolio:
                    new_portfolio.add(row["Ticker"])
    
    return {
        "universe": universe_name,
        "label": config["label"],
        "date": datetime.now().strftime("%Y-%m-%d"),
        "gold_ratio": gold_ratio,
        "gold_threshold": gold_threshold,
        "gold_signal_index": gold_signal_index,
        "go_gold": go_gold,
        "vix": vix_value,
        "vix_threshold": vix_threshold,
        "use_fast_lookback": use_fast_lookback,
        "lookback": f"{lookback_long}d/{lookback_short}d",
        "current_holdings": sorted(current_holdings),
        "new_portfolio": sorted(new_portfolio),
        "to_buy": sorted(new_portfolio - current_holdings),
        "to_sell": sorted(current_holdings - new_portfolio),
        "to_keep": sorted(current_holdings & new_portfolio),
        "scores": scores.head(10) if not scores.empty else pd.DataFrame(),
        "top_n": top_n,
        "buffer": f"{entry_rank}/{exit_rank}",
    }


# ============================================================
# OUTPUT FORMATTING
# ============================================================

def print_signal(signal):
    """Pretty-print a trading signal."""
    s = signal
    label = s["label"]
    
    print(f"\n{'═' * 60}")
    print(f"  {label}")
    print(f"  Signal Date: {s['date']}")
    print(f"{'═' * 60}")
    
    # Regime info
    ratio_str = f"{s['gold_ratio']:.2f}" if s['gold_ratio'] else "N/A"
    vix_str = f"{s['vix']:.1f}" if s['vix'] else "N/A"
    print(f"  {s['gold_signal_index']}/XAUUSD: {ratio_str} (threshold: ≥{s['gold_threshold']})")
    print(f"  VIX: {vix_str}", end="")
    if s['vix_threshold']:
        print(f" (threshold: >{s['vix_threshold']})", end="")
    if s['use_fast_lookback']:
        print(f" ⚡ FAST LOOKBACK", end="")
    print(f"\n  Lookback: {s['lookback']} | Buffer: {s['buffer']} | Positions: {s['top_n']}")
    
    print(f"{'─' * 60}")
    
    if s['go_gold']:
        print(f"  🟡 GOLD ROTATION ACTIVE")
        print(f"  Action: Hold GLD (or XAUUSD equivalent)")
        if s['current_holdings']:
            print(f"  Sell: {', '.join(s['current_holdings'])}")
    else:
        if s['to_keep']:
            print(f"  ✅ KEEP: {', '.join(s['to_keep'])}")
        if s['to_sell']:
            print(f"  🔴 SELL: {', '.join(s['to_sell'])}")
        if s['to_buy']:
            print(f"  🟢 BUY:  {', '.join(s['to_buy'])}")
            # Show leveraged equivalents
            lev = [LEVERAGED_ETF_MAP.get(t, t) for t in s['to_buy']]
            if lev != s['to_buy']:
                print(f"       Lev: {', '.join(lev)}")
        
        if not s['to_sell'] and not s['to_buy'] and s['new_portfolio']:
            print(f"  → No changes. Hold: {', '.join(s['new_portfolio'])}")
        elif s['new_portfolio']:
            portfolio_str = ', '.join(s['new_portfolio'])
            lev_portfolio = [LEVERAGED_ETF_MAP.get(t, t) for t in s['new_portfolio']]
            print(f"\n  Portfolio: {portfolio_str}")
            print(f"  Leveraged: {', '.join(lev_portfolio)}")
    
    # Top 10 scores
    if not s['scores'].empty:
        print(f"\n  {'Rank':<5} {'Ticker':<8} {'Score':<8} {'MR_12':<8} {'MR_6':<8}")
        print(f"  {'─' * 40}")
        for _, row in s['scores'].head(10).iterrows():
            ticker = row['Ticker']
            marker = "◀" if ticker in s['new_portfolio'] else ""
            print(f"  {row['Rank']:<5} {ticker:<8} {row['Momentum_Score']:.3f}   {row['MR_12']:.2f}    {row['MR_6']:.2f}  {marker}")
    
    print(f"{'═' * 60}")


def _update_index_signals(signals):
    """Inject live signals section into index.html."""
    index_path = Path(__file__).parent / "dashboards" / "index.html"
    if not index_path.exists() or not signals:
        return
    
    # Get actual last data date from parquet
    cached = load_cached_prices()
    data_date = cached.index[-1].strftime("%Y-%m-%d") if cached is not None else signals[0]["date"]
    
    rows_html = ""
    for s in signals:
        label = s["label"]
        folder = s["universe"]
        
        if s["go_gold"]:
            action = "🟡 GOLD"
            holdings_str = "GLD"
            color = "#fff3cd"
        else:
            holdings_str = ", ".join(s["new_portfolio"][:5])
            lev_str = ", ".join([LEVERAGED_ETF_MAP.get(t, t) for t in s["new_portfolio"][:5]])
            action = "📈 STOCKS"
            color = "#d4edda"
        
        ratio_str = f"{s['gold_ratio']:.2f}" if s['gold_ratio'] else "N/A"
        vix_str = f"{s['vix']:.0f}" if s['vix'] else "N/A"
        
        rows_html += f'<tr style="background:{color};">'
        rows_html += f'<td style="font-weight:bold;"><a href="{folder}/dashboard.html">{label}</a></td>'
        rows_html += f'<td>{action}</td>'
        rows_html += f'<td><strong>{holdings_str}</strong></td>'
        if not s["go_gold"]:
            rows_html += f'<td style="font-size:10px;color:#666;">{lev_str}</td>'
        else:
            rows_html += f'<td>-</td>'
        rows_html += f'<td>{ratio_str}</td>'
        rows_html += f'<td>{vix_str}</td>'
        rows_html += f'</tr>\n'
    
    signals_section = f'''<div id="liveSignals" style="background:white;border-radius:10px;padding:20px;box-shadow:0 2px 8px rgba(0,0,0,0.1);margin-bottom:20px;border-left:4px solid #1f77b4;">
<h2 style="margin:0 0 12px 0;">🔔 Live Signals <span style="font-size:12px;color:#666;font-weight:normal;">Data as of: {data_date}</span></h2>
<table style="width:100%;border-collapse:collapse;font-size:12px;">
<thead><tr style="background:#f8f9fa;"><th style="padding:8px;text-align:left;">Universe</th><th>Signal</th><th>Holdings</th><th>Leveraged</th><th>Index/Gold</th><th>VIX</th></tr></thead>
<tbody>
{rows_html}</tbody></table>
</div>
'''
    
    # Read current index.html and inject/replace the signals section
    content = index_path.read_text()
    
    # Check if signals section already exists
    if '<div id="liveSignals"' in content:
        # Replace existing
        import re
        content = re.sub(
            r'<div id="liveSignals".*?</div>\n',
            signals_section,
            content,
            flags=re.DOTALL
        )
    else:
        # Insert after <h1> line
        content = content.replace(
            '<div class="controls">',
            signals_section + '<div class="controls">'
        )
    
    index_path.write_text(content)
    print(f"  ✅ Updated index.html with live signals")


def _get_last_holdings(universe_name):
    """Auto-detect current holdings from the last row of backtest CSV."""
    csv_path = Path(__file__).parent / "dashboards" / universe_name / "backtest_wide.csv"
    if not csv_path.exists():
        return []
    df = pd.read_csv(csv_path)
    if df.empty:
        return []
    last_row = df.iloc[-1]
    holdings = []
    for col in df.columns:
        if col.endswith("_Pct") and pd.notna(last_row[col]) and last_row[col] != "":
            ticker = col.replace("_Pct", "")
            if ticker not in ("Portfolio_Return", "Benchmark_Return", "Leveraged_Return"):
                holdings.append(ticker)
    return holdings


# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Live Trading Signal Generator")
    parser.add_argument("--universe", type=str, help="Single universe (default: nasdaq100_vix)")
    parser.add_argument("--holdings", type=str, help="Current holdings comma-separated (e.g., NVDA,AVGO,APP)")
    parser.add_argument("--all", action="store_true", help="Run all universes")
    parser.add_argument("--refresh", action="store_true", help="Force re-download all price data")
    parser.add_argument("--dashboard", action="store_true", help="Regenerate backtests + dashboards after updating prices")
    args = parser.parse_args()
    
    # Parse holdings — auto-detect from last backtest if not provided
    if args.holdings:
        holdings = args.holdings.split(",")
    else:
        # Auto-detect from last month's backtest output
        holdings = _get_last_holdings(args.universe or "nasdaq100_vix")
    
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║          MOMENTUM STRATEGY — LIVE SIGNALS                  ║")
    print(f"║          {datetime.now().strftime('%Y-%m-%d %H:%M')}                              ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    
    # Step 1: Update price cache (incremental unless --refresh)
    print("\n📊 Updating price data...")
    update_prices(force_refresh=args.refresh)
    
    # Step 2: Generate signals
    if args.universe:
        if args.universe not in UNIVERSE_CONFIGS:
            print(f"Unknown universe: {args.universe}")
            print(f"Available: {', '.join(sorted(UNIVERSE_CONFIGS.keys()))}")
            return
        universes = [args.universe]
    elif args.all:
        universes = list(UNIVERSE_CONFIGS.keys())
    else:
        # Default: run the main ones
        universes = ["nasdaq100_vix"]
    
    all_signals = []
    for universe in universes:
        try:
            signal = generate_signal(universe, holdings if universe == universes[0] else None)
            print_signal(signal)
            all_signals.append(signal)
        except Exception as e:
            print(f"\n  ❌ Error for {universe}: {e}")
            import traceback
            traceback.print_exc()
    
    # Regenerate backtests + dashboards if requested
    if args.dashboard:
        print(f"\n{'═' * 60}")
        print("  📊 Regenerating backtests & dashboards...")
        print(f"{'═' * 60}")
        from core import run_backtest as rb
        from generate_dashboard import generate_dashboard
        
        dash_universes = universes if not args.all else list(UNIVERSE_CONFIGS.keys())
        for universe in dash_universes:
            try:
                print(f"\n  [{universe}] Running backtest...", flush=True)
                rb(universe)
                print(f"  [{universe}] Generating dashboard...")
                generate_dashboard(universe)
            except Exception as e:
                print(f"  [{universe}] ❌ {e}")
        
        # Update index.html with live signals
        _update_index_signals(all_signals)
        print(f"\n  ✅ All dashboards regenerated.")


if __name__ == "__main__":
    main()
