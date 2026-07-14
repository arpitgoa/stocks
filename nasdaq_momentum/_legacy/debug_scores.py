"""
Debug: compare momentum scores between original and optimized at a specific date.
"""
import numpy as np
import pandas as pd
from pathlib import Path
from run_backtest import calculate_momentum_scores, load_prices_for_universe, load_membership
from run_backtest_optimized import calculate_momentum_scores_vectorized
from universe_config import get_config

UNIVERSES_DIR = Path.home() / "Documents" / "workspace" / "historical-index-universe-data" / "universes"

config = get_config("nasdaq100")
prices = load_prices_for_universe("nasdaq100", config)

# Date where divergence first appears
rebal_date = pd.Timestamp("2003-04-30")  # month before the divergence
cutoff_idx = prices.index.searchsorted(rebal_date)

membership_df = load_membership("nasdaq100")
ts = rebal_date
mask = (membership_df["EntryDate"] <= ts) & ((membership_df["ExitDate"].isna()) | (membership_df["ExitDate"] > ts))
universe = membership_df.loc[mask, "Symbol"].tolist()

print(f"Date: {rebal_date.date()}, Universe size: {len(universe)}, cutoff_idx: {cutoff_idx}")

# Original
orig = calculate_momentum_scores(prices, universe, rebal_date)
orig = orig.head(10).reset_index(drop=True)
orig.index += 1

# Optimized
opt = calculate_momentum_scores_vectorized(prices, universe, cutoff_idx)
opt = opt.head(10).reset_index(drop=True)
opt.index += 1

print("\n--- ORIGINAL top 10 ---")
print(orig[["Ticker", "MR_12", "MR_6", "Momentum_Score"]].to_string())

print("\n--- OPTIMIZED top 10 ---")
print(opt[["Ticker", "MR_12", "MR_6", "Momentum_Score"]].to_string())

# Check specific tickers
check = set(orig["Ticker"]) | set(opt["Ticker"])
orig_map = orig.set_index("Ticker")
opt_map  = opt.set_index("Ticker")
print("\n--- Score diff for tickers in either top 10 ---")
for t in sorted(check):
    o = orig_map.loc[t, "Momentum_Score"] if t in orig_map.index else None
    v = opt_map.loc[t, "Momentum_Score"]  if t in opt_map.index  else None
    match = "✓" if (o is not None and v is not None and abs(o - v) < 1e-6) else "✗"
    print(f"  {match} {t:20s}  orig={str(round(o,6)) if o else 'N/A':12s}  opt={str(round(v,6)) if v else 'N/A':12s}")
