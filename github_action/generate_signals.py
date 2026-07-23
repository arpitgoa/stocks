"""
Generate momentum signals for all universes.
Same algorithm as the backtest: 12M/6M vol-adjusted momentum, buffer logic, gold rotation.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from config import UNIVERSES, SIGNAL_TICKERS, LEVERAGED_ETF_MAP
from fetch_constituents import get_constituents
from update_prices import PRICES_FILE


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
        log_rets = np.log(ts.iloc[end_idx-lookback_long:end_idx+1] / ts.iloc[end_idx-lookback_long:end_idx+1].shift(1)).dropna()
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
    df["Momentum_Score"] = df["Weighted_Z"].apply(lambda z: (1+z) if z >= 0 else 1/(1-z))
    df["Rank"] = df["Momentum_Score"].rank(ascending=False).astype(int)
    return df.sort_values("Momentum_Score", ascending=False).reset_index(drop=True)


def generate_signal(universe_name, prices, prev_holdings=None):
    """Generate signal for one universe."""
    config = UNIVERSES[universe_name]
    source = config.get("constituents_source", "")
    members = get_constituents(source)
    
    if not members:
        return None
    
    top_n = config["top_n"]
    entry_rank = config["entry_rank"]
    exit_rank = config["exit_rank"]
    gold_threshold = config["gold_threshold"]
    gold_signal = config["gold_signal_index"]
    vix_threshold = config.get("vix_threshold")
    
    if prev_holdings is None:
        prev_holdings = set()
    
    # Gold rotation check
    gold_ratio = None
    go_gold = False
    top3_ref = []
    if gold_signal in prices.columns and "GC=F" in prices.columns:
        idx_val = prices[gold_signal].dropna().iloc[-1] if prices[gold_signal].notna().any() else None
        gold_val = prices["GC=F"].dropna().iloc[-1] if prices["GC=F"].notna().any() else None
        if idx_val and gold_val and gold_val > 0:
            gold_ratio = idx_val / gold_val
            if gold_ratio >= gold_threshold:
                go_gold = True
                # Still calculate top 3 for reference (use standard 252/126 lookback)
                try:
                    ref_scores = calculate_scores(prices, members, 252, 126)
                    if not ref_scores.empty:
                        top3_ref = ref_scores.head(3)["Ticker"].tolist()
                except:
                    pass
        print(f"    Gold check: {gold_signal}={idx_val}, GC=F={gold_val}, ratio={gold_ratio}, threshold={gold_threshold}, go_gold={go_gold}")
    else:
        print(f"    Gold check SKIPPED: {gold_signal} in prices={gold_signal in prices.columns}, GC=F in prices={'GC=F' in prices.columns}")
    
    # VIX check
    vix_val = None
    use_fast = False
    if "^VIX" in prices.columns:
        vix_series = prices["^VIX"].dropna()
        if len(vix_series) > 0:
            vix_val = vix_series.iloc[-1]
            if vix_threshold and vix_val > vix_threshold:
                use_fast = True
    
    # Score
    if use_fast:
        lookback_long = config.get("vix_fast_long", 126)
        lookback_short = config.get("vix_fast_short", 42)
        w12, w6 = 0.5, 0.5  # More responsive blend in panic
    else:
        lookback_long, lookback_short = 252, 126
        w12, w6 = 0.7, 0.3  # Favor sustained trend in calm markets
    
    scores = calculate_scores(prices, members, lookback_long, lookback_short,
                              weight_12=w12, weight_6=w6)
    
    # Buffer logic
    new_portfolio = set()
    if not scores.empty and not go_gold:
        ranked = dict(zip(scores["Ticker"], scores["Rank"]))
        retained = {t for t in prev_holdings if t in ranked and ranked[t] <= exit_rank}
        new_portfolio = retained.copy()
        for _, row in scores.iterrows():
            if len(new_portfolio) >= top_n: break
            if row["Ticker"] not in new_portfolio and row["Rank"] <= entry_rank:
                new_portfolio.add(row["Ticker"])
        if len(new_portfolio) < top_n:
            for _, row in scores.iterrows():
                if len(new_portfolio) >= top_n: break
                if row["Ticker"] not in new_portfolio:
                    new_portfolio.add(row["Ticker"])
    
    return {
        "universe": universe_name,
        "label": config["label"],
        "go_gold": go_gold,
        "gold_ratio": gold_ratio,
        "gold_threshold": gold_threshold,
        "vix": vix_val,
        "vix_fast": use_fast,
        "portfolio": sorted(new_portfolio),
        "leveraged": [LEVERAGED_ETF_MAP.get(t, t) for t in sorted(new_portfolio)],
        "top3": top3_ref if go_gold else sorted(new_portfolio)[:3],
        "top10": scores.head(10)[["Ticker", "Rank", "Momentum_Score"]].to_dict("records") if not scores.empty else [],
    }


def generate_all_signals():
    """Generate signals for all universes."""
    if not PRICES_FILE.exists():
        print("❌ No price data. Run update_prices.py first.")
        return []
    
    prices = pd.read_parquet(PRICES_FILE)
    prices.index = pd.to_datetime(prices.index)
    
    signals = []
    for universe_name in UNIVERSES:
        try:
            signal = generate_signal(universe_name, prices)
            if signal:
                signals.append(signal)
        except Exception as e:
            print(f"  ❌ {universe_name}: {e}")
    
    return signals


if __name__ == "__main__":
    signals = generate_all_signals()
    for s in signals:
        if s["go_gold"]:
            print(f"  {s['label']:<30} 🟡 GOLD (ratio={s['gold_ratio']:.2f})")
        else:
            print(f"  {s['label']:<30} 📈 {', '.join(s['portfolio'])}")
