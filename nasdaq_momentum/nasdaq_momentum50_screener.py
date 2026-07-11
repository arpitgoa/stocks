"""
NASDAQ Momentum 50 Screener
============================
Applies the Nifty Midcap150 Momentum 50 methodology to NASDAQ stocks.

Uses yfinance to pull real price data for NASDAQ-100 constituents,
calculates Normalized Momentum Scores, and ranks the top 50.
"""

import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

# ============================================================
# STEP 1: NASDAQ-100 Universe
# ============================================================

# NASDAQ-100 constituents (as of mid-2025 — update as needed)
NASDAQ_100 = [
    "AAPL", "MSFT", "AMZN", "NVDA", "META", "GOOGL", "GOOG", "AVGO", "TSLA", "COST",
    "NFLX", "AMD", "ADBE", "PEP", "CSCO", "TMUS", "LIN", "INTC", "INTU", "AMGN",
    "TXN", "CMCSA", "QCOM", "HON", "AMAT", "ISRG", "BKNG", "VRTX", "ADP", "SBUX",
    "GILD", "MU", "ADI", "MDLZ", "LRCX", "REGN", "PANW", "SNPS", "CDNS", "KLAC",
    "MELI", "PYPL", "CRWD", "CTAS", "MAR", "ORLY", "MNST", "ABNB", "FTNT", "DASH",
    "MRVL", "CEG", "KDP", "DXCM", "NXPI", "AEP", "PCAR", "ROST", "KHC", "ODFL",
    "PAYX", "EXC", "FAST", "CTSH", "VRSK", "CPRT", "EA", "XEL", "GEHC", "IDXX",
    "BKR", "FANG", "TTWO", "ON", "CSGP", "DDOG", "ANSS", "CDW", "ZS", "TEAM",
    "TTD", "GFS", "ILMN", "WBD", "MRNA", "LCID", "RIVN", "ARM", "SMCI", "APP",
    "PLTR", "MSTR", "COIN", "HOOD", "AXON", "WDAY", "LULU", "CHTR", "BIIB", "DLTR",
]

print("=" * 70)
print("NASDAQ MOMENTUM 50 SCREENER")
print("(Applying Nifty Midcap150 Momentum 50 methodology to NASDAQ-100)")
print("=" * 70)
print(f"\nUniverse: {len(NASDAQ_100)} NASDAQ stocks")
print(f"Date: {datetime.now().strftime('%Y-%m-%d')}")
print("\nDownloading price data from Yahoo Finance...")

# ============================================================
# STEP 2: Download Price Data
# ============================================================

# Need ~14 months of data to compute 12-month return skipping last month
end_date = datetime.now()
start_date = end_date - timedelta(days=400)  # ~14 months

# Download all at once for efficiency
data = yf.download(
    NASDAQ_100,
    start=start_date.strftime('%Y-%m-%d'),
    end=end_date.strftime('%Y-%m-%d'),
    progress=False,
    auto_adjust=True,
)

# Extract closing prices
prices = data['Close'] if 'Close' in data.columns.get_level_values(0) else data

# Drop stocks with insufficient data
min_days = 240  # need at least ~12 months
prices = prices.dropna(axis=1, thresh=min_days)
prices = prices.ffill()

print(f"Successfully downloaded data for {prices.shape[1]} stocks")
print(f"Date range: {prices.index[0].strftime('%Y-%m-%d')} to {prices.index[-1].strftime('%Y-%m-%d')}")
print(f"Trading days: {len(prices)}")


# ============================================================
# STEP 3: Calculate Momentum Scores
# ============================================================

def calculate_momentum_scores(prices_df):
    """
    Calculate Normalized Momentum Score for each stock
    following NSE's methodology:
    
    1. 12M return (skip last month) / annualized volatility = MR_12
    2. 6M return (skip last month) / annualized volatility = MR_6
    3. Z-score both across the universe
    4. Weighted Avg Z = 50% * Z_12 + 50% * Z_6
    5. Normalized Score = (1+Z) if Z>=0, else (1-Z)^-1
    """
    results = []
    n = len(prices_df)
    
    for stock in prices_df.columns:
        p = prices_df[stock].dropna()
        if len(p) < min_days:
            continue
        
        # Prices at key points
        # M-1: ~1 month ago (skip last 21 trading days)
        # M-7: ~7 months ago
        # M-13: ~13 months ago
        price_now = p.iloc[-1]
        price_m1 = p.iloc[-22] if len(p) > 22 else p.iloc[0]     # ~1 month ago
        price_m7 = p.iloc[-148] if len(p) > 148 else p.iloc[0]   # ~7 months ago
        price_m13 = p.iloc[0]                                      # ~13 months ago
        
        # Returns
        return_12m = (price_m1 / price_m13) - 1
        return_6m = (price_m1 / price_m7) - 1
        
        # Annualized volatility of log returns (1 year lookback)
        log_returns = np.diff(np.log(p.values[-252:])) if len(p) >= 252 else np.diff(np.log(p.values))
        sigma_p = np.std(log_returns) * np.sqrt(252)
        
        if sigma_p <= 0 or np.isnan(sigma_p):
            continue
        
        # Momentum Ratios
        mr_12 = return_12m / sigma_p
        mr_6 = return_6m / sigma_p
        
        # Get market cap from yfinance (use last close * shares as proxy)
        results.append({
            'Ticker': stock,
            'Price': price_now,
            'Return_12M': return_12m,
            'Return_6M': return_6m,
            'Volatility': sigma_p,
            'MR_12': mr_12,
            'MR_6': mr_6,
        })
    
    df = pd.DataFrame(results)
    
    if df.empty:
        return df
    
    # Z-Scores across the universe
    df['Z_MR_12'] = (df['MR_12'] - df['MR_12'].mean()) / df['MR_12'].std()
    df['Z_MR_6'] = (df['MR_6'] - df['MR_6'].mean()) / df['MR_6'].std()
    
    # Weighted Average Z Score (50/50)
    df['Weighted_Avg_Z'] = 0.5 * df['Z_MR_12'] + 0.5 * df['Z_MR_6']
    
    # Normalized Momentum Score
    df['Momentum_Score'] = df['Weighted_Avg_Z'].apply(
        lambda z: (1 + z) if z >= 0 else (1 - z) ** -1
    )
    
    # Sort by score
    df = df.sort_values('Momentum_Score', ascending=False).reset_index(drop=True)
    df['Rank'] = range(1, len(df) + 1)
    
    return df


print("\nCalculating momentum scores...")
scores = calculate_momentum_scores(prices)

if scores.empty:
    print("ERROR: No valid scores calculated. Check data availability.")
    exit(1)


# ============================================================
# STEP 4: Display Results
# ============================================================

print(f"\n{'=' * 70}")
print(f"TOP 50 STOCKS BY NORMALIZED MOMENTUM SCORE")
print(f"{'=' * 70}")
print(f"\n{'Rank':<5} {'Ticker':<7} {'Price':>8} {'12M Ret':>9} {'6M Ret':>8} {'Vol':>7} {'Z_Avg':>7} {'Score':>7}")
print("-" * 62)

top_50 = scores.head(50)
for _, row in top_50.iterrows():
    print(f"{int(row['Rank']):<5} {row['Ticker']:<7} ${row['Price']:>7.2f} "
          f"{row['Return_12M']:>8.1%} {row['Return_6M']:>7.1%} "
          f"{row['Volatility']:>6.1%} {row['Weighted_Avg_Z']:>6.2f} "
          f"{row['Momentum_Score']:>6.3f}")

# Bottom 10
print(f"\n{'=' * 70}")
print(f"BOTTOM 10 — WEAKEST MOMENTUM")
print(f"{'=' * 70}")
print(f"\n{'Rank':<5} {'Ticker':<7} {'Price':>8} {'12M Ret':>9} {'6M Ret':>8} {'Vol':>7} {'Score':>7}")
print("-" * 55)

bottom_10 = scores.tail(10)
for _, row in bottom_10.iterrows():
    print(f"{int(row['Rank']):<5} {row['Ticker']:<7} ${row['Price']:>7.2f} "
          f"{row['Return_12M']:>8.1%} {row['Return_6M']:>7.1%} "
          f"{row['Volatility']:>6.1%} {row['Momentum_Score']:>6.3f}")


# ============================================================
# STEP 5: Summary Stats
# ============================================================

print(f"\n{'=' * 70}")
print("SUMMARY")
print(f"{'=' * 70}")
print(f"""
Stocks analyzed:     {len(scores)}
Top 50 avg return:   12M = {top_50['Return_12M'].mean():.1%}, 6M = {top_50['Return_6M'].mean():.1%}
Top 50 avg vol:      {top_50['Volatility'].mean():.1%}
Bottom 10 avg ret:   12M = {bottom_10['Return_12M'].mean():.1%}, 6M = {bottom_10['Return_6M'].mean():.1%}
Bottom 10 avg vol:   {bottom_10['Volatility'].mean():.1%}

Score range:         {scores['Momentum_Score'].min():.3f} to {scores['Momentum_Score'].max():.3f}
Median score:        {scores['Momentum_Score'].median():.3f}
""")

# ============================================================
# STEP 6: Sector-like grouping by theme
# ============================================================

tech_hw = ["AAPL", "NVDA", "AVGO", "AMD", "INTC", "QCOM", "MU", "MRVL", "TXN", "ADI", 
           "NXPI", "LRCX", "AMAT", "KLAC", "ON", "ARM", "SMCI", "GFS"]
software = ["MSFT", "ADBE", "INTU", "SNPS", "CDNS", "CRWD", "PANW", "FTNT", "DDOG", 
            "ZS", "TEAM", "WDAY", "PLTR", "APP", "TTD", "ANSS", "EA", "TTWO"]
internet = ["AMZN", "GOOGL", "GOOG", "META", "NFLX", "TSLA", "BKNG", "ABNB", "MELI",
            "PYPL", "DASH", "COIN", "HOOD", "CSGP"]
healthcare = ["AMGN", "GILD", "VRTX", "REGN", "ISRG", "IDXX", "DXCM", "GEHC", "BIIB",
              "MRNA", "ILMN"]

def get_sector_summary(sector_name, tickers, scores_df):
    sector_scores = scores_df[scores_df['Ticker'].isin(tickers)]
    if sector_scores.empty:
        return
    in_top50 = sector_scores[sector_scores['Rank'] <= 50]
    print(f"  {sector_name}: {len(in_top50)}/{len(sector_scores)} in top 50, "
          f"avg score = {sector_scores['Momentum_Score'].mean():.3f}")

print(f"{'=' * 70}")
print("THEME BREAKDOWN (stocks in top 50)")
print(f"{'=' * 70}")
get_sector_summary("Semis/HW ", tech_hw, scores)
get_sector_summary("Software ", software, scores)
get_sector_summary("Internet ", internet, scores)
get_sector_summary("Healthcare", healthcare, scores)
