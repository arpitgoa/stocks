"""
NASDAQ-100 Momentum Strategy Backtest
======================================
Applies the Nifty Midcap150 Momentum 50 methodology to NASDAQ-100 stocks.

Strategy:
- Universe: NASDAQ-100 constituents (point-in-time)
- Signal: Normalized Momentum Score (6M + 12M risk-adjusted returns)
- Selection: Top 20 stocks by momentum score
- Weighting: Factor-tilt (market cap × momentum score), 5% cap
- Rebalance: Semi-annually (June & December)
- Benchmark: QQQ (buy & hold)

Data: nasdaq100_daily_closes.csv (20 years of daily close prices)
"""

import numpy as np
import pandas as pd
from datetime import datetime
from scipy.optimize import brentq


# ============================================================
# HELPER FUNCTIONS: XIRR & MAX DRAWDOWN
# ============================================================

def xirr(cashflows):
    """
    Calculate XIRR given a list of (date, amount) tuples.
    Negative = investment, Positive = withdrawal/final value.
    """
    if not cashflows:
        return 0.0
    
    dates = [cf[0] for cf in cashflows]
    amounts = [cf[1] for cf in cashflows]
    
    # Days from first cashflow
    d0 = dates[0]
    days = [(d - d0).days / 365.25 for d in dates]
    
    def npv(rate):
        return sum(amt / (1 + rate) ** t for amt, t in zip(amounts, days))
    
    try:
        return brentq(npv, -0.5, 10.0, maxiter=1000)
    except (ValueError, RuntimeError):
        return 0.0


def max_drawdown(values):
    """
    Calculate maximum drawdown from a series of portfolio values.
    Returns (max_dd_pct, peak_date, trough_date).
    """
    peak = values[0]
    peak_idx = 0
    max_dd = 0
    max_dd_peak_idx = 0
    max_dd_trough_idx = 0
    
    for i, val in enumerate(values):
        if val > peak:
            peak = val
            peak_idx = i
        dd = (peak - val) / peak
        if dd > max_dd:
            max_dd = dd
            max_dd_peak_idx = peak_idx
            max_dd_trough_idx = i
    
    return max_dd, max_dd_peak_idx, max_dd_trough_idx

# ============================================================
# CONFIG
# ============================================================

TOP_N = 3                   # Number of stocks to hold
ENTRY_RANK = 3              # New stock must be in top 3 to enter
EXIT_RANK = 7               # Existing stock stays unless it drops below rank 7
MAX_WEIGHT = 0.05           # 5% cap per stock
REBALANCE_MONTHS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]  # Monthly
MIN_HISTORY_DAYS = 252      # Need at least 1 year of price data
SKIP_LAST_MONTH = 5         # Skip last ~1 week (testing 5-day vs 21-day)
START_YEAR = 1995           # First rebalance (need 1994 for lookback)
ABSOLUTE_MOMENTUM = False   # Disabled — stay fully invested
NDX_GOLD_THRESHOLD = 7.0    # If NDX/XAUUSD >= 7.0, hold gold instead of stocks

# ============================================================
# LOAD DATA
# ============================================================

from load_norgate_data import load_prices as _load_norgate_prices, get_members_at_date
from pathlib import Path

NORGATE_DIR = Path.home() / "Documents" / "workspace" / "historical-index-universe-data"

print("Loading price data...")
prices = _load_norgate_prices()
print(f"Loaded: {prices.shape[0]} days × {prices.shape[1]} tickers")
print(f"Date range: {prices.index[0].date()} to {prices.index[-1].date()}")

# Load NDX index and XAUUSD (gold spot) from Norgate for the ratio signal
ndx_price_file = NORGATE_DIR / "prices" / "$NDX__320.csv"
xau_price_file = NORGATE_DIR / "prices" / "XAUUSD__527909.csv"

if ndx_price_file.exists():
    ndx_df = pd.read_csv(ndx_price_file, usecols=["Date", "Close"], index_col="Date", parse_dates=True)
    prices["$NDX"] = ndx_df["Close"]
    print(f"$NDX loaded: {ndx_df.index[0].date()} to {ndx_df.index[-1].date()}")

if xau_price_file.exists():
    xau_df = pd.read_csv(xau_price_file, usecols=["Date", "Close"], index_col="Date", parse_dates=True)
    prices["XAUUSD"] = xau_df["Close"]
    print(f"XAUUSD loaded: {xau_df.index[0].date()} to {xau_df.index[-1].date()}")

# Load QQQ benchmark (from Norgate)
qqq_price_file = NORGATE_DIR / "prices" / "QQQ__145303.csv"
if qqq_price_file.exists():
    qqq_df = pd.read_csv(qqq_price_file, usecols=["Date", "Close"], index_col="Date", parse_dates=True)
    prices["QQQ"] = qqq_df["Close"]
    print(f"QQQ benchmark loaded: {qqq_df.index[0].date()} to {qqq_df.index[-1].date()}")

# Load GLD (from Norgate)
gld_price_file = NORGATE_DIR / "prices" / "GLD__155510.csv"
if gld_price_file.exists():
    gld_df = pd.read_csv(gld_price_file, usecols=["Date", "Close"], index_col="Date", parse_dates=True)
    prices["GLD"] = gld_df["Close"]
    print(f"GLD loaded: {gld_df.index[0].date()} to {gld_df.index[-1].date()}")

# Load leveraged ETF prices (only available from ~2022+)
import os
if os.path.exists("nasdaq100_daily_closes.csv"):
    lev_df = pd.read_csv("nasdaq100_daily_closes.csv", index_col="Date", parse_dates=True)
    from leveraged_config import LEVERAGED_ETF_MAP
    for lev_ticker in set(LEVERAGED_ETF_MAP.values()):
        if lev_ticker in lev_df.columns and lev_ticker not in prices.columns:
            prices[lev_ticker] = lev_df[lev_ticker]
    print(f"Leveraged ETF data loaded for: {[t for t in set(LEVERAGED_ETF_MAP.values()) if t in prices.columns]}")

HAS_BENCHMARK = "QQQ" in prices.columns
if not HAS_BENCHMARK:
    print("\nNote: QQQ not in data file. Will skip benchmark comparison.")
    print("  Add QQQ to your download to enable benchmark comparison.\n")


# ============================================================
# MOMENTUM SCORE CALCULATION
# ============================================================

def calculate_momentum_scores(prices_df, universe_tickers, rebal_date):
    """
    Calculate Normalized Momentum Scores for all stocks in the universe
    at a given rebalance date.
    
    Returns DataFrame with scores, sorted descending.
    """
    # Get prices up to rebalance date
    available_prices = prices_df.loc[:rebal_date]
    
    results = []
    
    for ticker in universe_tickers:
        if ticker not in available_prices.columns:
            continue
        
        p = available_prices[ticker].dropna()
        
        # Need at least 1 year + 1 month of data
        if len(p) < MIN_HISTORY_DAYS + SKIP_LAST_MONTH:
            continue
        
        # Skip last month (as per NSE methodology)
        p = p.iloc[:-SKIP_LAST_MONTH]
        
        if len(p) < MIN_HISTORY_DAYS:
            continue
        
        # --- 12-month price return ---
        # Price at end vs price 252 days ago
        price_end = p.iloc[-1]
        price_12m_ago = p.iloc[-252] if len(p) >= 252 else p.iloc[0]
        return_12m = (price_end / price_12m_ago) - 1
        
        # --- 6-month price return ---
        price_6m_ago = p.iloc[-126] if len(p) >= 126 else p.iloc[0]
        return_6m = (price_end / price_6m_ago) - 1
        
        # --- Annualized volatility (1 year of log returns) ---
        recent_prices = p.iloc[-252:] if len(p) >= 252 else p
        log_returns = np.diff(np.log(recent_prices.values))
        sigma_p = np.std(log_returns) * np.sqrt(252)
        
        if sigma_p <= 0 or np.isnan(sigma_p):
            continue
        
        # --- Momentum Ratios ---
        mr_12 = return_12m / sigma_p
        mr_6 = return_6m / sigma_p
        
        results.append({
            'Ticker': ticker,
            'Return_12M': return_12m,
            'Return_6M': return_6m,
            'Volatility': sigma_p,
            'MR_12': mr_12,
            'MR_6': mr_6,
        })
    
    if not results:
        return pd.DataFrame()
    
    df = pd.DataFrame(results)
    
    # --- Z-Scores ---
    df['Z_MR_12'] = (df['MR_12'] - df['MR_12'].mean()) / df['MR_12'].std()
    df['Z_MR_6'] = (df['MR_6'] - df['MR_6'].mean()) / df['MR_6'].std()
    
    # --- Weighted Average Z Score (50/50) ---
    df['Weighted_Avg_Z'] = 0.5 * df['Z_MR_12'] + 0.5 * df['Z_MR_6']
    
    # --- Normalized Momentum Score ---
    df['Momentum_Score'] = df['Weighted_Avg_Z'].apply(
        lambda z: (1 + z) if z >= 0 else (1 - z) ** -1
    )
    
    # Sort by score descending
    df = df.sort_values('Momentum_Score', ascending=False).reset_index(drop=True)
    
    # Apply absolute momentum gate: only keep stocks with positive 12M return
    if ABSOLUTE_MOMENTUM:
        positive_mask = df['Return_12M'] > 0
        df_filtered = df[positive_mask].reset_index(drop=True)
        cash_pct = 1.0 - (len(df_filtered) / max(TOP_N, 1)) if len(df_filtered) < TOP_N else 0.0
        df_filtered.attrs['cash_pct'] = cash_pct
        return df_filtered
    
    return df


# ============================================================
# WEIGHT CALCULATION
# ============================================================

def calculate_weights(top_stocks_df, max_weight=MAX_WEIGHT, method="momentum_tilt"):
    """
    Calculate weights.
    method: "equal" or "momentum_tilt"
    """
    df = top_stocks_df.copy()
    
    if method == "equal":
        df['Weight'] = 1.0 / len(df)
        return df[['Ticker', 'Momentum_Score', 'Weight']]
    
    # Momentum tilt: weight proportional to momentum score
    df['Raw_Weight'] = df['Momentum_Score'] / df['Momentum_Score'].sum()
    
    # Apply cap iteratively
    for _ in range(10):  # iterate to redistribute excess
        excess = df['Raw_Weight'].clip(upper=max_weight) - df['Raw_Weight']
        total_excess = -excess[excess < 0].sum()
        
        df['Raw_Weight'] = df['Raw_Weight'].clip(upper=max_weight)
        
        if total_excess < 0.001:
            break
        
        # Redistribute excess to uncapped stocks
        uncapped = df['Raw_Weight'] < max_weight
        if uncapped.sum() > 0:
            df.loc[uncapped, 'Raw_Weight'] += total_excess / uncapped.sum()
    
    # Final normalization
    df['Weight'] = df['Raw_Weight'] / df['Raw_Weight'].sum()
    
    return df[['Ticker', 'Momentum_Score', 'Weight']]


# ============================================================
# BACKTEST ENGINE
# ============================================================

def run_backtest(prices_df, start_year=START_YEAR, top_n=TOP_N, weight_method="momentum_tilt", max_weight=MAX_WEIGHT, weight_reset_months=None):
    """
    Run the full backtest with rank buffer:
    - Existing holdings stay unless they drop below EXIT_RANK
    - New stocks only enter if they rank at or above ENTRY_RANK
    - Target portfolio size: TOP_N stocks
    - weight_reset_months: if set, only recalculate weights in these months
      (otherwise use previous weights for retained stocks, equal-share for new adds)
    """
    # Generate rebalance dates
    rebal_dates = []
    last_date = prices_df.index[-1]
    for year in range(start_year, last_date.year + 1):
        for month in REBALANCE_MONTHS:
            try:
                month_data = prices_df.loc[f"{year}-{month:02d}"]
                if len(month_data) > 0:
                    rebal_dates.append(month_data.index[-1])
            except KeyError:
                continue  # Month doesn't exist in data yet
    
    # Remove any rebalance dates too close to end of data
    rebal_dates = [d for d in rebal_dates if d < last_date - pd.Timedelta(days=5)]
    
    print(f"\nRebalance dates: {len(rebal_dates)} ({rebal_dates[0].date()} to {rebal_dates[-1].date()})")
    print(f"Buffer: entry <= rank {ENTRY_RANK}, exit > rank {EXIT_RANK}")
    
    # Track portfolio value
    portfolio_value = 100000.0  # Start with $100K
    monthly_contribution = 1000.0  # DCA $1,000 per month
    total_invested = 100000.0  # Track total capital deployed
    holdings_history = []
    current_holdings = set()  # Track current portfolio for buffer logic
    prev_weights = None       # Track previous weights for carry-forward
    total_trades = 0
    
    for i, rebal_date in enumerate(rebal_dates):
        # Determine next rebalance date
        if i + 1 < len(rebal_dates):
            next_rebal = rebal_dates[i + 1]
        else:
            next_rebal = prices_df.index[-1]
        
        # NDX/XAUUSD ratio check — if above threshold, hold gold (XAUUSD)
        if NDX_GOLD_THRESHOLD and '$NDX' in prices_df.columns and 'XAUUSD' in prices_df.columns:
            ndx_p = prices_df['$NDX'].loc[:rebal_date].dropna()
            xau_p = prices_df['XAUUSD'].loc[:rebal_date].dropna()
            if len(ndx_p) > 0 and len(xau_p) > 0:
                ratio = ndx_p.iloc[-1] / xau_p.iloc[-1]
                if ratio >= NDX_GOLD_THRESHOLD:
                    # Hold gold this month — use XAUUSD returns
                    hold_period = prices_df.loc[rebal_date:next_rebal]
                    gold_hold = hold_period['XAUUSD'].dropna()
                    gold_ret = (gold_hold.iloc[-1] / gold_hold.iloc[0]) - 1 if len(gold_hold) >= 2 else 0
                    portfolio_value *= (1 + gold_ret)
                    portfolio_value += monthly_contribution
                    total_invested += monthly_contribution
                    
                    print(f"  {rebal_date.date()} → {next_rebal.date()}: "
                          f"Ret={gold_ret:+.1%}, Val=${portfolio_value:.2f} | "
                          f"GOLD (NDX/XAUUSD={ratio:.2f})")
                    
                    holdings_history.append({
                        'Rebal_Date': rebal_date,
                        'Next_Rebal': next_rebal,
                        'Period_Return': gold_ret,
                        'Portfolio_Value': portfolio_value,
                        'Holdings': [{'Ticker': 'XAUUSD', 'Weight': 1.0}],
                        'Trades': 0,
                        'Top7': ['GOLD (NDX/XAUUSD={:.2f})'.format(ratio)],
                        'Removed': [],
                        'Added': ['XAUUSD'],
                    })
                    continue
        
        # Get universe at this date
        universe = get_members_at_date(rebal_date.strftime('%Y-%m-%d'))
        
        # Calculate momentum scores
        scores = calculate_momentum_scores(prices_df, universe, rebal_date)
        
        if scores.empty:
            print(f"  {rebal_date.date()}: No stocks qualify, 100% cash")
            # Record cash period
            if i + 1 < len(rebal_dates):
                next_rebal = rebal_dates[i + 1]
            else:
                next_rebal = prices_df.index[-1]
            holdings_history.append({
                'Rebal_Date': rebal_date,
                'Next_Rebal': next_rebal,
                'Period_Return': 0.0,
                'Portfolio_Value': portfolio_value,
                'Holdings': [],
                'Trades': 0,
            })
            continue
        
        # Use however many stocks qualify (may be < top_n with absolute momentum)
        effective_top_n = min(top_n, len(scores))
        
        # --- BUFFER LOGIC ---
        # Assign ranks
        scores['Rank'] = range(1, len(scores) + 1)
        ranked_tickers = dict(zip(scores['Ticker'], scores['Rank']))
        
        # Check how many stocks qualify (absolute momentum may reduce the pool)
        available_count = len(scores)
        cash_pct = max(0, (top_n - available_count) / top_n) if available_count < top_n else 0.0
        
        # Step 1: Keep existing holdings that haven't dropped below EXIT_RANK
        retained = set()
        for ticker in current_holdings:
            if ticker in ranked_tickers and ranked_tickers[ticker] <= EXIT_RANK:
                retained.add(ticker)
        
        # Step 2: Add new stocks from top ENTRY_RANK to fill up to effective_top_n
        new_portfolio = retained.copy()
        for _, row in scores.iterrows():
            if len(new_portfolio) >= effective_top_n:
                break
            ticker = row['Ticker']
            if ticker not in new_portfolio and row['Rank'] <= ENTRY_RANK:
                new_portfolio.add(ticker)
        
        # Step 3: If still under effective_top_n, fill from top ranks regardless
        if len(new_portfolio) < effective_top_n:
            for _, row in scores.iterrows():
                if len(new_portfolio) >= effective_top_n:
                    break
                if row['Ticker'] not in new_portfolio:
                    new_portfolio.add(row['Ticker'])
        
        # Cash percentage (if fewer than TOP_N stocks qualify)
        cash_pct = max(0, (top_n - len(new_portfolio)) / top_n)
        
        # Count trades
        trades_this_period = len(new_portfolio - current_holdings) + len(current_holdings - new_portfolio)
        added_tickers = sorted(new_portfolio - current_holdings)
        removed_tickers = sorted(current_holdings - new_portfolio)
        total_trades += trades_this_period
        current_holdings = new_portfolio
        
        # Get scores for selected stocks
        selected_scores = scores[scores['Ticker'].isin(new_portfolio)].copy()
        
        # Calculate weights — full reset or carry forward
        is_weight_reset_month = (weight_reset_months is None) or (rebal_date.month in weight_reset_months)
        
        if is_weight_reset_month or prev_weights is None:
            # Full weight recalculation
            weighted = calculate_weights(selected_scores, max_weight=max_weight, method=weight_method)
            prev_weights = dict(zip(weighted['Ticker'], weighted['Weight']))
        else:
            # Carry forward weights for retained stocks, give new stocks equal share
            new_tickers = new_portfolio - retained
            
            # Get current drifted weights from price changes (simulate drift)
            # For simplicity: keep previous weights for retained, split remaining among new
            total_retained_weight = sum(prev_weights.get(t, 0) for t in retained if t in new_portfolio)
            remaining_weight = 1.0 - total_retained_weight
            new_weight_each = remaining_weight / len(new_tickers) if new_tickers else 0
            
            weight_dict = {}
            for t in new_portfolio:
                if t in retained and t in prev_weights:
                    weight_dict[t] = prev_weights[t]
                else:
                    weight_dict[t] = new_weight_each
            
            # Normalize to sum to 1
            total = sum(weight_dict.values())
            weight_dict = {k: v/total for k, v in weight_dict.items()}
            
            weighted = selected_scores[['Ticker', 'Momentum_Score']].copy()
            weighted['Weight'] = weighted['Ticker'].map(weight_dict)
            weighted = weighted.dropna(subset=['Weight'])
            
            prev_weights = dict(zip(weighted['Ticker'], weighted['Weight']))
        
        # Holding period (already set at top of loop)
        
        # Get prices during holding period
        hold_period = prices_df.loc[rebal_date:next_rebal]
        
        if len(hold_period) < 2:
            continue
        
        # Calculate portfolio return during holding period
        period_returns = []
        for _, row in weighted.iterrows():
            ticker = row['Ticker']
            weight = row['Weight']
            
            if ticker not in hold_period.columns:
                continue
            
            ticker_prices = hold_period[ticker].dropna()
            if len(ticker_prices) < 2:
                continue
            
            ticker_return = (ticker_prices.iloc[-1] / ticker_prices.iloc[0]) - 1
            period_returns.append(weight * ticker_return)
        
        portfolio_return = sum(period_returns)
        # Scale down by cash portion (cash earns 0%)
        if cash_pct > 0:
            portfolio_return = portfolio_return * (1 - cash_pct)
        portfolio_value *= (1 + portfolio_return)
        
        # DCA: add monthly contribution after returns are applied
        portfolio_value += monthly_contribution
        total_invested += monthly_contribution
        
        # Record
        top_5 = ", ".join(weighted['Ticker'].head(5).tolist())
        retained_count = len(retained)
        new_count = len(new_portfolio) - retained_count
        cash_str = f", Cash={cash_pct:.0%}" if cash_pct > 0 else ""
        print(f"  {rebal_date.date()} → {next_rebal.date()}: "
              f"Ret={portfolio_return:+.1%}, Val=${portfolio_value:.2f} | "
              f"Kept={retained_count}, New={new_count}, Trades={trades_this_period}{cash_str} | "
              f"Top 5: {top_5}")
        
        holdings_history.append({
            'Rebal_Date': rebal_date,
            'Next_Rebal': next_rebal,
            'Period_Return': portfolio_return,
            'Portfolio_Value': portfolio_value,
            'Holdings': weighted[['Ticker', 'Weight']].to_dict('records'),
            'Trades': trades_this_period,
            'Top7': scores.head(10)['Ticker'].tolist(),
            'Removed': removed_tickers,
            'Added': added_tickers,
        })
    
    print(f"\n  Total trades over backtest: {total_trades}")
    print(f"  Avg trades per rebalance: {total_trades / len(holdings_history):.1f}")
    print(f"  Total invested (DCA): ${total_invested:,.2f}")
    
    return portfolio_value, holdings_history, None


# ============================================================
# RUN BACKTEST
# ============================================================

print("\n" + "=" * 70)
print("RUNNING BACKTEST: NASDAQ-100 MOMENTUM TOP 20")
print("=" * 70)

# Test 1: Equal weight
print("\n>>> EQUAL WEIGHT <<<")
final_eq, holdings_eq, _ = run_backtest(prices, weight_method="equal")

# Test 2: Momentum tilt with 10% cap (monthly membership, 6-month weight reset)
print("\n>>> MOMENTUM TILT 10% cap (6-month weight reset) <<<")
final_tilt, holdings_tilt, _ = run_backtest(prices, weight_method="momentum_tilt", max_weight=0.10, weight_reset_months=[6, 12])

# ============================================================
# BENCHMARK (QQQ Buy & Hold)
# ============================================================

print("\n" + "=" * 70)
print("RESULTS COMPARISON")
print("=" * 70)

for label, final_value, holdings in [
    ("Equal Weight", final_eq, holdings_eq),
    ("Momentum Tilt 10% cap (6-mo weight reset)", final_tilt, holdings_tilt),
]:
    first_rebal = holdings[0]['Rebal_Date'] if holdings else None
    last_rebal = holdings[-1]['Next_Rebal'] if holdings else None
    
    if first_rebal and last_rebal:
        years = (last_rebal - first_rebal).days / 365.25
        num_months = len(holdings)
        total_invested_amt = 100000 + (num_months * 1000)
        profit = final_value - total_invested_amt
        multiple = final_value / total_invested_amt
        
        print(f"\n{label}:")
        print(f"  Period: {first_rebal.date()} to {last_rebal.date()} ({years:.1f} years)")
        print(f"  Total invested: ${total_invested_amt:,.0f} ($100K + {num_months} × $1K DCA)")
        print(f"  Ending value:   ${final_value:,.0f}")
        print(f"  Profit:         ${profit:,.0f}")
        print(f"  Multiple:       {multiple:.1f}x on invested capital")
        
        # XIRR calculation
        cashflows = [
            (first_rebal, -100000)  # Initial investment
        ]
        for h in holdings:
            cashflows.append((h['Rebal_Date'], -1000))  # Monthly DCA
        cashflows.append((last_rebal, final_value))  # Final value as withdrawal
        
        xirr_rate = xirr(cashflows)
        print(f"  XIRR:           {xirr_rate:.1%}")
        
        # Max drawdown
        port_values = [100000]
        port_dates = [first_rebal]
        for h in holdings:
            port_values.append(h['Portfolio_Value'])
            port_dates.append(h['Next_Rebal'])
        
        mdd, peak_idx, trough_idx = max_drawdown(port_values)
        print(f"  Max Drawdown:   -{mdd:.1%} ({port_dates[peak_idx].strftime('%Y-%m')} → {port_dates[trough_idx].strftime('%Y-%m')})")

# Benchmark (NDX index — uses QQQ where available, $NDX for pre-1999)
if holdings_eq:
    first_rebal = holdings_eq[0]['Rebal_Date']
    last_rebal = holdings_eq[-1]['Next_Rebal']
    years = (last_rebal - first_rebal).days / 365.25
    num_months = len(holdings_eq)
    total_invested_amt = 100000 + (num_months * 1000)
    
    # Simulate NDX/QQQ DCA — use QQQ where available, fall back to $NDX
    qqq_value = 100000.0
    for h in holdings_eq:
        # Try QQQ first, fall back to $NDX
        bench_ret = 0
        if 'QQQ' in prices.columns:
            qqq_period = prices.loc[h['Rebal_Date']:h['Next_Rebal'], 'QQQ'].dropna()
            if len(qqq_period) >= 2:
                bench_ret = (qqq_period.iloc[-1] / qqq_period.iloc[0]) - 1
        if bench_ret == 0 and '$NDX' in prices.columns:
            ndx_period = prices.loc[h['Rebal_Date']:h['Next_Rebal'], '$NDX'].dropna()
            if len(ndx_period) >= 2:
                bench_ret = (ndx_period.iloc[-1] / ndx_period.iloc[0]) - 1
        qqq_value *= (1 + bench_ret)
        qqq_value += 1000  # Same DCA
    
    print(f"\nBenchmark: NDX/QQQ (Buy & Hold + same DCA)")
    print(f"  Total invested: ${total_invested_amt:,.0f}")
    print(f"  Ending value:   ${qqq_value:,.0f}")
    print(f"  Profit:         ${qqq_value - total_invested_amt:,.0f}")
    print(f"  Multiple:       {qqq_value / total_invested_amt:.1f}x on invested capital")
    
    # XIRR
    qqq_cashflows = [(holdings_eq[0]['Rebal_Date'], -100000)]
    for h in holdings_eq:
        qqq_cashflows.append((h['Rebal_Date'], -1000))
    qqq_cashflows.append((holdings_eq[-1]['Next_Rebal'], qqq_value))
    qqq_xirr = xirr(qqq_cashflows)
    print(f"  XIRR:           {qqq_xirr:.1%}")
    
    # Max Drawdown
    qqq_values = [100000.0]
    qqq_dates = [holdings_eq[0]['Rebal_Date']]
    qqq_val_track = 100000.0
    for h in holdings_eq:
        bench_ret = 0
        if 'QQQ' in prices.columns:
            qqq_period = prices.loc[h['Rebal_Date']:h['Next_Rebal'], 'QQQ'].dropna()
            if len(qqq_period) >= 2:
                bench_ret = (qqq_period.iloc[-1] / qqq_period.iloc[0]) - 1
        if bench_ret == 0 and '$NDX' in prices.columns:
            ndx_period = prices.loc[h['Rebal_Date']:h['Next_Rebal'], '$NDX'].dropna()
            if len(ndx_period) >= 2:
                bench_ret = (ndx_period.iloc[-1] / ndx_period.iloc[0]) - 1
        qqq_val_track *= (1 + bench_ret)
        qqq_val_track += 1000
        qqq_values.append(qqq_val_track)
        qqq_dates.append(h['Next_Rebal'])
    
    qqq_mdd, qqq_peak_idx, qqq_trough_idx = max_drawdown(qqq_values)
    print(f"  Max Drawdown:   -{qqq_mdd:.1%} ({qqq_dates[qqq_peak_idx].strftime('%Y-%m')} → {qqq_dates[qqq_trough_idx].strftime('%Y-%m')})")


# ============================================================
# SAVE RESULTS — WIDE FORMAT (tickers as columns)
# ============================================================

# Get all unique tickers across all periods, sorted alphabetically
all_tickers_used = sorted(set(
    holding['Ticker']
    for h in holdings_tilt
    for holding in h['Holdings']
))

print(f"\nBuilding wide-format CSV with {len(all_tickers_used)} ticker columns...")

wide_rows = []
for h in holdings_tilt:
    rebal_date = h['Rebal_Date']
    next_rebal = h['Next_Rebal']
    port_start = h['Portfolio_Value'] / (1 + h['Period_Return'])
    port_end = h['Portfolio_Value']
    
    # Build a dict of ticker -> weight for this period
    hold_period = prices.loc[rebal_date:next_rebal]
    ticker_weights = {}
    for holding in h['Holdings']:
        ticker_weights[holding['Ticker']] = holding['Weight']
    
    row = {
        'Start_Date': rebal_date.strftime('%Y-%m-%d'),
        'End_Date': next_rebal.strftime('%Y-%m-%d'),
        'Portfolio_Start': round(port_start, 2),
        'Portfolio_End': round(port_end, 2),
        'Portfolio_Return_Pct': round(h['Period_Return'] * 100, 2),
    }
    
    # Benchmark return for same period (QQQ where available, $NDX as fallback)
    bench_ret = None
    if 'QQQ' in prices.columns:
        qqq_period = prices.loc[rebal_date:next_rebal, 'QQQ'].dropna()
        if len(qqq_period) >= 2:
            bench_ret = (qqq_period.iloc[-1] / qqq_period.iloc[0]) - 1
    if bench_ret is None and '$NDX' in prices.columns:
        ndx_period = prices.loc[rebal_date:next_rebal, '$NDX'].dropna()
        if len(ndx_period) >= 2:
            bench_ret = (ndx_period.iloc[-1] / ndx_period.iloc[0]) - 1
    row['QQQ_Return_Pct'] = round(bench_ret * 100, 2) if bench_ret is not None else ""
    
    # Top 7 ranked tickers and changes
    row['Top7'] = ", ".join(h.get('Top7', []))
    added = h.get('Added', [])
    removed = h.get('Removed', [])
    if added and removed:
        row['Changes'] = ", ".join([f"{r}→{a}" for r, a in zip(removed, added)])
    elif added:
        row['Changes'] = "+" + ", +".join(added)
    elif removed:
        row['Changes'] = "-" + ", -".join(removed)
    else:
        row['Changes'] = ""
    
    # Calculate leveraged portfolio return for this period
    from leveraged_config import LEVERAGED_ETF_MAP
    hold_period = prices.loc[rebal_date:next_rebal]
    lev_ret = 0
    for ticker, weight in ticker_weights.items():
        lev_ticker = LEVERAGED_ETF_MAP.get(ticker)
        if lev_ticker and lev_ticker in hold_period.columns:
            lp = hold_period[lev_ticker].dropna()
            if len(lp) >= 2:
                lev_ret += weight * ((lp.iloc[-1] / lp.iloc[0]) - 1)
                continue
        # Fallback to stock
        if ticker in hold_period.columns:
            tp = hold_period[ticker].dropna()
            if len(tp) >= 2:
                lev_ret += weight * ((tp.iloc[-1] / tp.iloc[0]) - 1)
    row['Leveraged_Return_Pct'] = round(lev_ret * 100, 2)
    for ticker in all_tickers_used:
        if ticker in ticker_weights:
            weight_pct = round(ticker_weights[ticker] * 100, 2)
            dollar_amt = round(port_start * ticker_weights[ticker], 2)
            
            # Calculate return for this ticker during the period
            if ticker in hold_period.columns:
                tp = hold_period[ticker].dropna()
                if len(tp) >= 2:
                    ret = round(((tp.iloc[-1] / tp.iloc[0]) - 1) * 100, 2)
                else:
                    ret = ""
            else:
                ret = ""
            
            row[f"{ticker}_Pct"] = weight_pct
            row[f"{ticker}_$"] = dollar_amt
            row[f"{ticker}_Ret"] = ret
            
            # Leveraged ETF return for this ticker
            lev_ticker = LEVERAGED_ETF_MAP.get(ticker)
            if lev_ticker and lev_ticker in hold_period.columns:
                lp = hold_period[lev_ticker].dropna()
                if len(lp) >= 2:
                    row[f"{ticker}_LevRet"] = round(((lp.iloc[-1] / lp.iloc[0]) - 1) * 100, 2)
                else:
                    row[f"{ticker}_LevRet"] = ret  # fallback to stock
            else:
                row[f"{ticker}_LevRet"] = ret  # no lev ETF, use stock
        else:
            row[f"{ticker}_Pct"] = ""
            row[f"{ticker}_$"] = ""
            row[f"{ticker}_Ret"] = ""
            row[f"{ticker}_LevRet"] = ""
    
    wide_rows.append(row)

wide_df = pd.DataFrame(wide_rows)
wide_df.to_csv("backtest_wide_holdings.csv", index=False)
print(f"Saved to: nasdaq_momentum/backtest_wide_holdings.csv")
print(f"  Shape: {wide_df.shape[0]} months × {wide_df.shape[1]} columns")
print(f"  Tickers: {', '.join(all_tickers_used[:10])} ... ({len(all_tickers_used)} total)")
