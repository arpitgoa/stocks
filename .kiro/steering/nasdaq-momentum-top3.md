---
inclusion: auto
---

# NASDAQ-100 Momentum Top 3 Strategy

## Project Location
- Workspace: `/Users/ajhanwa/workspace/stocks/nasdaq_momentum/`
- Main backtest: `backtest.py`
- Dashboard generator: `generate_html.py`
- Interactive dashboard: `momentum_backtest_dashboard.html`
- Strategy docs: `STRATEGY_README.md`

## Core Strategy Parameters

### Stock Selection
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

## Overlays

### LEAPS Options
- Buy 1-year 20% OTM calls when stock enters top 3
- Premium: 4% of stock price, Risk: 3% of portfolio per position
- Exit: stock drops below rank 7 OR at 12-month expiry
- Results: 51.3% CAGR, 17% win rate, 39:1 win/loss ratio

### Leveraged ETFs
- Use 2x leveraged single-stock ETFs when available (NVDA→NVDL, MU→MUU, TSLA→TSLL)
- Mapping in `leveraged_config.py`
- Results: 58.4% CAGR with leverage vs 48% without

## Key Design Decisions
1. **Concentration wins:** Top 3 beats top 5/10/20 by wide margin
2. **Buffer is critical:** 3/7 buffer prevents churn and lets winners ride
3. **Monthly rebalance:** Weekly too noisy, quarterly too slow
4. **12M/6M lookback is optimal:** Shorter is noisy, longer is too slow
5. **NSE vol adjustment:** Battle-tested methodology
6. **GLD rotation adds value** when QQQ/GLD ≥ 2.0 (tech overvalued vs gold)
7. **Never use absolute momentum (cash gate):** Misses recoveries badly (23.9% CAGR)

## Data Files
| File | Purpose |
|------|---------|
| `nasdaq100_daily_closes.csv` | All price data (302 tickers) |
| `qqq_daily_closes.csv` | QQQ benchmark prices |
| `nasdaq100_membership_by_year.json` | Verified NDX membership per year |
| `nasdaq100_scd2.csv` | SCD2 format membership history |
| `backtest_results.csv` | Monthly backtest output |
| `backtest_detailed_holdings.csv` | Detailed holdings per month |
| `backtest_wide_holdings.csv` | Wide-format holdings |

## Scripts
| File | Purpose |
|------|---------|
| `backtest.py` | Main backtest engine |
| `generate_html.py` | Generates interactive dashboard |
| `download_data.py` | yfinance download script |
| `build_scd2_membership.py` | Builds SCD2 membership from Wikipedia |
| `build_historical_membership.py` | Historical membership builder |
| `nasdaq100_historical_changes.py` | Membership lookup function |
| `leveraged_config.py` | Leveraged ETF ticker mapping |
| `nasdaq_momentum50_screener.py` | Screener for top 50 momentum |

## Current Holdings (July 2026)
- **Stocks:** MU, STX, WDC
- **Leveraged:** MUU, STX, WDC
- **QQQ/GLD ratio:** 1.89 (below 2.0 → holding stocks)
- **Top 7 ranked:** SNDK, WDC, MU, STX, INTC, MRVL, LITE
