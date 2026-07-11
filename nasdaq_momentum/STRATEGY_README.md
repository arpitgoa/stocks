# NASDAQ-100 Momentum Top 3 Strategy

## Final Strategy Parameters

### Core Strategy (Stocks)
- **Universe:** NASDAQ-100 constituents (point-in-time verified membership)
- **Selection:** Top 3 stocks by Normalized Momentum Score
- **Entry buffer:** Stock must rank ≤ 3 to enter
- **Exit buffer:** Stock stays unless it drops below rank 7
- **Weighting:** Equal weight (~33% each), reset monthly
- **Rebalance:** Monthly (last trading day)
- **GLD Rotation:** If QQQ/GLD ≥ 2.0, hold 100% GLD instead of stocks

### Momentum Score Calculation (NSE Methodology)
1. **12M return** (skip last 5 trading days): Price(end) / Price(252 days ago) - 1
2. **6M return** (skip last 5 trading days): Price(end) / Price(126 days ago) - 1
3. **Volatility (σ):** Annualized std dev of daily log returns over 252 days
4. **Momentum Ratios:** MR_12 = 12M return / σ, MR_6 = 6M return / σ
5. **Z-Scores:** Z_12 = (MR_12 - mean) / std, Z_6 = (MR_6 - mean) / std (across full universe)
6. **Weighted Z:** 50% × Z_12 + 50% × Z_6
7. **Normalized Score:** If Z ≥ 0 → (1+Z), else → (1-Z)⁻¹

### Results (2016–2026, $100K + $1K/mo DCA)
- **XIRR:** 53.1%
- **Ending value:** $10.9M
- **Multiple:** 48.4x on invested capital
- **Max Drawdown:** -25.9%

---

## LEAPS Options Strategy (Overlay)
- **Entry:** Buy 1-year 20% OTM calls when stock enters top 3
- **Premium:** 4% of stock price
- **Risk:** 3% of portfolio per position
- **Exit:** Sell when stock drops below rank 7 OR at 12-month expiry
- **Re-entry:** If stock still held after expiry, open new LEAPS
- **Results:** $100K → $7.4M (51.3% CAGR), 17% win rate, 39:1 win/loss ratio

---

## Leveraged ETF Comparison
When a 2x leveraged single-stock ETF exists for a held stock, use it instead.
- Map: NVDA→NVDL, MU→MUU, TSLA→TSLL, etc. (see leveraged_config.py)
- Results: 58.4% CAGR with leverage vs 48% without

---

## Tests Performed & Rejected
| Test | Result | Decision |
|------|--------|----------|
| Top 1 stock | 38.6% CAGR, -54% DD | Too concentrated |
| Top 2 stocks | 46.0% CAGR, -39% DD | Too much drawdown |
| Top 3 stocks (3/7) | 48.0% CAGR, -26% DD | ✅ SELECTED |
| Top 4 stocks | 40.9% CAGR, -29% DD | Dilutes signal |
| Top 5 stocks | 39.7% CAGR, -24% DD | Dilutes signal |
| Top 10 stocks | 29.0% CAGR, -23% DD | Too diversified |
| Top 20 stocks | 24.9% CAGR, -28% DD | Essentially index |
| Weekly rebalance | 40.2% CAGR, -50% DD | Too noisy |
| Quarterly rebalance | 22.5% CAGR | Too slow |
| 6M/3M lookback | 35.9% CAGR, -18% DD | Less return |
| 3M/1M lookback | 14.5% CAGR | Way too noisy |
| Composite 30/20/30/20 | 42.1% CAGR, -36% DD | Worse than 50/50 |
| RSI filter (max <90) | 47.5% CAGR | No improvement |
| RSI filter (min >70) | 22.2% CAGR | Much worse |
| MA filter (P>200,P>150,50>150) | 47.3% CAGR, -31% DD | Redundant |
| Volatility filter (>30%) | 51.3% CAGR, -44% DD | More DD |
| No vol adjustment | 56.2% CAGR, -30% DD | Good but unproven |
| Vol^0.5 adjustment | 53.4% CAGR, -41% DD | More DD |
| Absolute momentum (cash gate) | 23.9% CAGR | Misses recovery |
| Monthly options (5% OTM) | Lost money | Win rate too low |
| Buffer 3/3 (no buffer) | 39.8% CAGR, -38% DD | Too much churn |
| Buffer 3/10 | 52.0% CAGR, -26% DD | Close to 3/7 |
| TQQQ/SOXL/GLD in universe | 48.4% CAGR | No improvement |
| QQQ/GLD ≥ 2.0 → hold GLD | 53.1% CAGR, -26% DD | ✅ ADDED |

---

## Files
| File | Purpose |
|------|---------|
| `backtest.py` | Main backtest engine |
| `generate_html.py` | Generates interactive dashboard |
| `momentum_backtest_dashboard.html` | Interactive results dashboard |
| `nasdaq100_daily_closes.csv` | All price data (302 tickers) |
| `qqq_daily_closes.csv` | QQQ benchmark prices |
| `nasdaq100_membership_by_year.json` | Verified NDX membership per year |
| `build_scd2_membership.py` | Builds SCD2 membership from Wikipedia |
| `nasdaq100_historical_changes.py` | Membership lookup function |
| `leveraged_config.py` | Leveraged ETF ticker mapping |
| `download_data.py` | yfinance download script (258 tickers) |

---

## Current Holdings (as of July 2026)
- **Stocks:** MU, STX, WDC
- **Leveraged:** MUU, STX, WDC
- **QQQ/GLD ratio:** 1.89 (below 2.0 → holding stocks)
- **Top 7 ranked:** SNDK, WDC, MU, STX, INTC, MRVL, LITE

---

## Key Insights
1. **Concentration wins:** Top 3 beats top 5/10/20 by wide margin
2. **Buffer is critical:** 3/7 buffer prevents churn and lets winners ride
3. **Monthly > Weekly > Quarterly** for rebalance frequency
4. **12M/6M lookback is optimal** — shorter is noisy, longer is too slow
5. **NSE vol adjustment works** — battle-tested methodology
6. **GLD rotation adds value** when QQQ/GLD ≥ 2.0 (tech overvalued vs gold)
7. **LEAPS options work** as overlay — 51% CAGR with only 9% capital at risk
8. **Momentum has 3 bad year types:** 2018 (-8%), 2019 (+3%), 2021 (-20%) — all regime changes
9. **Win rate is 61%** for individual stock-months, with +10.8% avg win vs -7.2% avg loss
10. **Max consecutive red streak:** 3 months (for any single stock)
