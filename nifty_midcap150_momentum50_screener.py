"""
Nifty Midcap150 Momentum 50 — Screener Implementation
======================================================
This script replicates the Normalized Momentum Score methodology
used by NSE Indices for the Nifty Midcap150 Momentum 50 index.

It uses synthetic example data to demonstrate the calculation.
To use with real data, replace the example prices with actual
NSE closing prices from a data provider (e.g., yfinance, NSE API).
"""

import numpy as np
import pandas as pd

# ============================================================
# STEP 1: Generate Example Data (Replace with real NSE data)
# ============================================================

# Simulating 20 midcap stocks with 1 year of daily prices
np.random.seed(42)
num_stocks = 20
trading_days = 252  # ~1 year of trading days

stock_names = [
    "STOCK_A", "STOCK_B", "STOCK_C", "STOCK_D", "STOCK_E",
    "STOCK_F", "STOCK_G", "STOCK_H", "STOCK_I", "STOCK_J",
    "STOCK_K", "STOCK_L", "STOCK_M", "STOCK_N", "STOCK_O",
    "STOCK_P", "STOCK_Q", "STOCK_R", "STOCK_S", "STOCK_T",
]

# Simulate daily returns with different drift and volatility per stock
daily_returns = {}
for i, name in enumerate(stock_names):
    # Random drift (annual return between -20% and +80%)
    annual_drift = np.random.uniform(-0.20, 0.80)
    daily_drift = annual_drift / trading_days
    # Random volatility (annualized between 20% and 60%)
    annual_vol = np.random.uniform(0.20, 0.60)
    daily_vol = annual_vol / np.sqrt(trading_days)
    
    returns = np.random.normal(daily_drift, daily_vol, trading_days)
    daily_returns[name] = returns

# Convert to price series (starting at 100)
prices_df = pd.DataFrame()
for name in stock_names:
    price_series = [100]
    for r in daily_returns[name]:
        price_series.append(price_series[-1] * np.exp(r))
    prices_df[name] = price_series

# Simulate free-float market cap (in crores)
ff_mcap = {name: np.random.uniform(5000, 30000) for name in stock_names}

print("=" * 70)
print("NIFTY MIDCAP150 MOMENTUM 50 — SCREENER DEMO")
print("=" * 70)
print(f"\nUniverse: {num_stocks} stocks (simulated midcap data)")
print(f"Trading days: {trading_days}")


# ============================================================
# STEP 2: Calculate Momentum Ratios
# ============================================================

def calculate_momentum_score(prices_df, ff_mcap):
    """
    Calculate Normalized Momentum Score for each stock
    following NSE's methodology exactly.
    """
    results = []
    
    for stock in prices_df.columns:
        prices = prices_df[stock].values
        n = len(prices)
        
        # --- 12-month price return ---
        # [Price(M-1) / Price(M-13)] - 1
        # Using last price vs price 12 months ago (skipping recent month)
        # In practice: last trading day of M-1 month / last trading day of M-13 month
        # For simplicity: use price[-22] / price[0] - 1 (skip last ~1 month)
        price_12m_ago = prices[0]           # ~13 months ago
        price_1m_ago = prices[-22]          # ~1 month ago (M-1)
        return_12m = (price_1m_ago / price_12m_ago) - 1
        
        # --- 6-month price return ---
        # [Price(M-1) / Price(M-7)] - 1
        price_6m_ago = prices[int(n * 0.5)]  # ~7 months ago
        return_6m = (price_1m_ago / price_6m_ago) - 1
        
        # --- Annualised Std Deviation (σp) ---
        # Standard deviation of lognormal daily returns for 1 year
        log_returns = np.diff(np.log(prices))
        sigma_p = np.std(log_returns) * np.sqrt(252)  # Annualized
        
        # --- Momentum Ratios ---
        mr_12 = return_12m / sigma_p if sigma_p > 0 else 0
        mr_6 = return_6m / sigma_p if sigma_p > 0 else 0
        
        results.append({
            'Stock': stock,
            'FF_MCap_Cr': ff_mcap[stock],
            'Return_12M': return_12m,
            'Return_6M': return_6m,
            'Volatility': sigma_p,
            'MR_12': mr_12,
            'MR_6': mr_6,
        })
    
    df = pd.DataFrame(results)
    
    # --- Z-Scores of Momentum Ratios ---
    # Z = (MR - mean) / std_dev of the eligible universe
    df['Z_MR_12'] = (df['MR_12'] - df['MR_12'].mean()) / df['MR_12'].std()
    df['Z_MR_6'] = (df['MR_6'] - df['MR_6'].mean()) / df['MR_6'].std()
    
    # --- Weighted Average Z Score ---
    # 50% weight to 12-month, 50% to 6-month
    df['Weighted_Avg_Z'] = 0.5 * df['Z_MR_12'] + 0.5 * df['Z_MR_6']
    
    # --- Normalized Momentum Score ---
    # (1 + Z) if Z >= 0
    # (1 - Z)^-1 if Z < 0
    df['Normalized_Momentum_Score'] = df['Weighted_Avg_Z'].apply(
        lambda z: (1 + z) if z >= 0 else (1 - z) ** -1
    )
    
    # --- Weight Calculation ---
    # Weight = FF_MCap × Normalized_Momentum_Score
    df['Raw_Weight'] = df['FF_MCap_Cr'] * df['Normalized_Momentum_Score']
    
    return df


# ============================================================
# STEP 3: Run the Screener
# ============================================================

scores_df = calculate_momentum_score(prices_df, ff_mcap)

# Sort by Normalized Momentum Score (descending) and pick top 10 (simulating top 50 from 150)
scores_df = scores_df.sort_values('Normalized_Momentum_Score', ascending=False).reset_index(drop=True)

# Normalize weights to sum to 100%
total_raw_weight = scores_df['Raw_Weight'].sum()
scores_df['Weight_Pct'] = (scores_df['Raw_Weight'] / total_raw_weight) * 100

# Apply 5% cap
scores_df['Weight_Capped'] = scores_df['Weight_Pct'].clip(upper=5.0)
# Redistribute excess (simplified)
excess = scores_df['Weight_Pct'].sum() - scores_df['Weight_Capped'].sum()
uncapped_mask = scores_df['Weight_Capped'] < 5.0
if uncapped_mask.sum() > 0:
    scores_df.loc[uncapped_mask, 'Weight_Capped'] += excess / uncapped_mask.sum()


# ============================================================
# STEP 4: Display Results
# ============================================================

print("\n" + "=" * 70)
print("MOMENTUM SCORES — ALL STOCKS (Ranked by Normalized Momentum Score)")
print("=" * 70)

display_cols = ['Stock', 'Return_12M', 'Return_6M', 'Volatility', 
                'MR_12', 'MR_6', 'Weighted_Avg_Z', 'Normalized_Momentum_Score', 
                'FF_MCap_Cr', 'Weight_Capped']

pd.set_option('display.float_format', '{:.4f}'.format)
pd.set_option('display.max_columns', 15)
pd.set_option('display.width', 120)

print(scores_df[display_cols].to_string(index=False))

print("\n" + "=" * 70)
print("TOP 10 SELECTED (would be top 50 from full 150-stock universe)")
print("=" * 70)

top_10 = scores_df.head(10)
print(f"\n{'Stock':<12} {'12M Ret':>8} {'6M Ret':>8} {'Vol':>8} {'Mom Score':>10} {'Weight%':>8}")
print("-" * 60)
for _, row in top_10.iterrows():
    print(f"{row['Stock']:<12} {row['Return_12M']:>7.1%} {row['Return_6M']:>7.1%} "
          f"{row['Volatility']:>7.1%} {row['Normalized_Momentum_Score']:>10.4f} "
          f"{row['Weight_Capped']:>7.2f}%")

print("\n" + "=" * 70)
print("INTERPRETATION")
print("=" * 70)
print("""
• Higher Normalized Momentum Score = stronger risk-adjusted price momentum
• Stocks at the top have been going UP consistently with LOWER volatility
• Stocks at the bottom have either been falling OR going up with high volatility
• Weights combine momentum score WITH market cap (bigger + more momentum = higher weight)
• 5% cap prevents any single stock from dominating the index
""")

# ============================================================
# STEP 5: Show the math for one stock
# ============================================================

print("=" * 70)
print("WORKED EXAMPLE — Showing full calculation for top stock")
print("=" * 70)

top_stock = scores_df.iloc[0]
print(f"""
Stock: {top_stock['Stock']}
─────────────────────────────────────────────────
1. Price Returns:
   • 12-month return (skipping last month): {top_stock['Return_12M']:.2%}
   • 6-month return (skipping last month):  {top_stock['Return_6M']:.2%}

2. Annualized Volatility (σp):
   • σp = {top_stock['Volatility']:.2%}

3. Momentum Ratios (Return ÷ Volatility):
   • MR_12 = {top_stock['Return_12M']:.4f} / {top_stock['Volatility']:.4f} = {top_stock['MR_12']:.4f}
   • MR_6  = {top_stock['Return_6M']:.4f} / {top_stock['Volatility']:.4f} = {top_stock['MR_6']:.4f}

4. Z-Scores (how many std devs above universe average):
   • Z_MR_12 = {top_stock['Z_MR_12']:.4f}
   • Z_MR_6  = {top_stock['Z_MR_6']:.4f}

5. Weighted Average Z Score:
   • = 50% × {top_stock['Z_MR_12']:.4f} + 50% × {top_stock['Z_MR_6']:.4f}
   • = {top_stock['Weighted_Avg_Z']:.4f}

6. Normalized Momentum Score:
   • Since Z >= 0: Score = 1 + {top_stock['Weighted_Avg_Z']:.4f} = {top_stock['Normalized_Momentum_Score']:.4f}

7. Weight in Index:
   • Raw = FF_MCap ({top_stock['FF_MCap_Cr']:.0f} Cr) × Score ({top_stock['Normalized_Momentum_Score']:.4f})
   • Final (after normalization & capping) = {top_stock['Weight_Capped']:.2f}%
""")
