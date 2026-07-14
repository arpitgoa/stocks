"""
Momentum Scoring Module
========================
Calculates momentum scores using the NSE methodology:
  1. 12M and 6M risk-adjusted returns (MR_12, MR_6)
  2. Z-score normalization across universe
  3. Weighted blend → Normalized Momentum Score

Supports:
  - Standard lookback (252d/126d)
  - VIX-adaptive fast lookback (126d/42d)
  - Precomputed scores from parquet (O(1) lookup)
"""

import numpy as np
import pandas as pd
from pathlib import Path
from .paths import PRECOMPUTED_MOMENTUM_PARQUET


# ============================================================
# PRECOMPUTED SCORES CACHE
# ============================================================

_precomputed_cache = None
_precomputed_by_date = None


def _load_precomputed():
    """Load precomputed momentum ratios from parquet."""
    global _precomputed_cache
    if _precomputed_cache is None:
        if not PRECOMPUTED_MOMENTUM_PARQUET.exists():
            return None
        print("  Loading precomputed momentum parquet...")
        _precomputed_cache = pd.read_parquet(
            PRECOMPUTED_MOMENTUM_PARQUET, columns=["Date", "Ticker", "MR_12", "MR_6"]
        )
        print(f"  Loaded: {len(_precomputed_cache):,} rows")
    return _precomputed_cache


def _get_precomputed_by_date():
    """Group precomputed scores by date for O(1) lookup. Built once on first use."""
    global _precomputed_by_date
    if _precomputed_by_date is None:
        df = _load_precomputed()
        if df is None:
            return None
        print("  Grouping precomputed scores by date...")
        _precomputed_by_date = {d: g.reset_index(drop=True) for d, g in df.groupby("Date")}
    return _precomputed_by_date


# ============================================================
# SCORE NORMALIZATION
# ============================================================

def _normalize_scores(df):
    """
    Apply Z-score normalization and compute final momentum score.
    
    Input df must have columns: Ticker, MR_12, MR_6
    Returns df with added: Z_12, Z_6, Weighted_Z, Momentum_Score
    """
    df = df.copy()
    df["Z_12"] = (df["MR_12"] - df["MR_12"].mean()) / df["MR_12"].std()
    df["Z_6"] = (df["MR_6"] - df["MR_6"].mean()) / df["MR_6"].std()
    df["Weighted_Z"] = 0.5 * df["Z_12"] + 0.5 * df["Z_6"]
    df["Momentum_Score"] = df["Weighted_Z"].apply(
        lambda z: (1 + z) if z >= 0 else 1 / (1 - z)
    )
    return df.sort_values("Momentum_Score", ascending=False).reset_index(drop=True)


# ============================================================
# LIVE SCORING FROM PRICES
# ============================================================

def _score_from_prices(prices_df, universe_tickers, cutoff_idx,
                       lookback_long=252, lookback_short=126, skip_days=5):
    """
    Calculate momentum scores from raw price data.
    
    Args:
        prices_df: Full price DataFrame (date index, ticker columns)
        universe_tickers: List of tickers to score
        cutoff_idx: Integer index into prices_df for the rebalance date
        lookback_long: Long lookback period in trading days (default 252 = 12M)
        lookback_short: Short lookback period in trading days (default 126 = 6M)
        skip_days: Skip last N days to avoid mean reversion (default 5)
        
    Returns:
        DataFrame with Ticker, MR_12, MR_6, Momentum_Score columns, sorted by score
    """
    tickers = [t for t in universe_tickers if t in prices_df.columns]
    results = []
    
    for ticker in tickers:
        ts = prices_df[ticker].iloc[:cutoff_idx + 1].dropna()
        end_idx = len(ts) - 1 - skip_days
        if end_idx < lookback_long:
            continue
            
        price_end = ts.iloc[end_idx]
        price_long = ts.iloc[end_idx - lookback_long]
        price_short = ts.iloc[end_idx - lookback_short]
        
        if price_long <= 0 or price_short <= 0:
            continue
            
        # Calculate volatility over the lookback period
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
    
    return _normalize_scores(pd.DataFrame(results))


# ============================================================
# PUBLIC API
# ============================================================

def calculate_momentum_scores(prices_df, universe_tickers, cutoff_idx,
                              min_history=252, skip_days=5):
    """
    Calculate momentum scores — uses precomputed parquet if available,
    falls back to live calculation from prices.
    
    Args:
        prices_df: Full price DataFrame
        universe_tickers: List of tickers in the universe at this date
        cutoff_idx: Integer index for the rebalance date
        min_history: Minimum required price history (default 252)
        skip_days: Skip last N trading days (default 5)
        
    Returns:
        DataFrame with Ticker, MR_12, MR_6, Momentum_Score, sorted desc
    """
    rebal_date = prices_df.index[cutoff_idx]
    by_date = _get_precomputed_by_date()

    if by_date is not None:
        # Find exact or nearest date within 5 days
        available = np.array(list(by_date.keys()), dtype="datetime64[ns]")
        diffs = np.abs(available - np.datetime64(rebal_date))
        nearest = pd.Timestamp(available[diffs.argmin()])
        if pd.Timedelta(diffs.min()) <= pd.Timedelta(days=5):
            subset = by_date[nearest]
            subset = subset[subset["Ticker"].isin(universe_tickers)].copy()
            if len(subset) >= 3:
                return _normalize_scores(subset[["Ticker", "MR_12", "MR_6"]])

    # Fallback: live calculation with standard lookback
    return _score_from_prices(prices_df, universe_tickers, cutoff_idx, 252, 126, skip_days)


def score_with_custom_lookback(prices_df, universe_tickers, rebal_date,
                               lookback_long=126, lookback_short=42, skip_days=5):
    """
    Score with custom lookback periods (used for VIX-adaptive mode).
    Always uses live calculation (precomputed only has 252/126).
    
    Args:
        prices_df: Full price DataFrame
        universe_tickers: List of tickers in universe
        rebal_date: The rebalance date (used for slicing)
        lookback_long: Custom long lookback (default 126 = 6M)
        lookback_short: Custom short lookback (default 42 = 2M)
        skip_days: Skip last N days (default 5)
    """
    results = []
    for ticker in universe_tickers:
        if ticker not in prices_df.columns:
            continue
        ts = prices_df[ticker].loc[:rebal_date].dropna()
        if len(ts) < lookback_long + skip_days:
            continue
        end_idx = len(ts) - 1 - skip_days
        if end_idx < lookback_long:
            continue
            
        price_end = ts.iloc[end_idx]
        price_long = ts.iloc[end_idx - lookback_long]
        price_short = ts.iloc[end_idx - lookback_short]
        
        if price_long <= 0 or price_short <= 0:
            continue
            
        log_rets = np.log(
            ts.iloc[end_idx - lookback_long:end_idx + 1] /
            ts.iloc[end_idx - lookback_long:end_idx + 1].shift(1)
        ).dropna()
        if len(log_rets) < 50:
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
    return _normalize_scores(pd.DataFrame(results))
