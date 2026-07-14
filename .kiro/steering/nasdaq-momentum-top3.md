---
inclusion: auto
---

# NASDAQ-100 Momentum Top 3 Strategy

## Project Location
- Workspace: `/Users/ajhanwa/Documents/workspace/stocks/nasdaq_momentum/`
- Data source: `/Users/ajhanwa/Documents/workspace/historical-index-universe-data/`
- Main backtest: `backtest.py`
- Data loader: `load_norgate_data.py` (loads 480 tickers from Norgate OHLC files)
- Dashboard generator: `generate_html.py`
- Interactive dashboard: `momentum_backtest_dashboard.html`
- Strategy docs: `STRATEGY_README.md`

## Core Strategy Parameters

### Stock Selection
- **Universe:** NASDAQ-100 constituents (point-in-time, SCD2 membership from Norgate)
- **Selection:** Top 3 stocks by Normalized Momentum Score
- **Entry buffer:** Stock must rank ≤ 3 to enter
- **Exit buffer:** Stock stays unless it drops below rank 7
- **Weighting:** Equal weight (~33% each), reset monthly
- **Rebalance:** Monthly (last trading day)
- **Gold Rotation:** If NDX/XAUUSD ≥ 7.0, hold 100% gold (XAUUSD) instead of stocks

### Momentum Score Calculation (NSE Methodology)
1. **12M return** (skip last 5 trading days): Price(end) / Price(252 days ago) - 1
2. **6M return** (skip last 5 trading days): Price(end) / Price(126 days ago) - 1
3. **Volatility (σ):** Annualized std dev of daily log returns over 252 days
4. **Momentum Ratios:** MR_12 = 12M return / σ, MR_6 = 6M return / σ
5. **Z-Scores:** Z_12 = (MR_12 - mean) / std, Z_6 = (MR_6 - mean) / std (across full universe)
6. **Weighted Z:** 50% × Z_12 + 50% × Z_6
7. **Normalized Score:** If Z ≥ 0 → (1+Z), else → (1-Z)⁻¹

### Gold Rotation Signal
- **Ratio:** NDX index price / XAUUSD (gold spot price)
- **Threshold:** ≥ 7.0 → hold 100% gold
- **Equivalent to:** QQQ/GLD ≥ 2.0 (correlation 0.9996 between the two ratios)
- **Why 7.0:** Tested thresholds 6.0-9.0; 7.0 gives best CAGR (35.7%) while cutting dot-com drawdown from -74% to -47%
- **Data:** NDX available from 1985, XAUUSD from 1982 — full backtest coverage from 1995

### Results (1995–2026, 31.4 years, $100K + $1K/mo DCA)
- **XIRR:** 33.8%
- **Ending value:** $1.33B
- **Multiple:** 2,776x on invested capital
- **Max Drawdown:** -46.9% (GFC 2007-10 → 2009-06)
- **Benchmark (NDX/QQQ):** 15.0% XIRR, 31.3x, -79.9% DD

## Overlays

### Leveraged ETFs (2022+ only)
- Use 2x leveraged single-stock ETFs when available (NVDA→NVDL, MU→MUU, TSLA→TSLL)
- Mapping in `leveraged_config.py`
- 1.8x daily-compounded backtest (full period): 100% CAGR, 633x, -51% DD
- Vol drag is minimal (~0.05%/mo) because momentum stocks trend strongly

### LEAPS Options
- Buy 1-year 20% OTM calls when stock enters top 3
- Premium: 4% of stock price, Risk: 3% of portfolio per position
- Exit: stock drops below rank 7 OR at 12-month expiry
- Results: 51.3% CAGR, 17% win rate, 39:1 win/loss ratio

## Filters & Ideas TESTED AND REJECTED

DO NOT re-test these. They have been thoroughly backtested and all make the strategy worse.

### 1. Shooting Star / Candlestick Filters
- **Test:** If previous month shows a shooting star pattern, skip entry
- **Result:** 93% false positive rate. Only 7% of shooting stars are followed by big drops. 85% of the time the stock stays flat or goes green. Useless as a filter.
- **Finding:** Shooting star pattern is real WITHIN crash months (87% of big drops have this shape) but does NOT appear the month BEFORE as an early warning.

### 2. QQQ Momentum Score Gate
- **Test:** Only hold stocks with momentum score higher than QQQ
- **Result:** Never triggers. Top 3 stocks ALWAYS have higher momentum than QQQ (1.2x-10x higher). QQQ ranks ~30-60 in the universe. Meaningless filter.

### 3. NDX Below 200 DMA → Hold NDX
- **Test:** When NDX is below its 200-day moving average, hold NDX index instead of momentum stocks
- **Result:** -3.3% CAGR (32.4% vs 35.7%), WORSE drawdown (-54% vs -47%), halved end value. Triggers 78 months (20% of time) — too often. Catches both crashes (good) AND corrections within uptrends (bad). Killed 2025-2026 where momentum stocks were up +173% but NDX briefly dipped below MA.

### 4. Stop Loss on All Holdings (-4% Below Previous Month Low)
- **Test:** If any held stock drops 4% below its previous month's low, sell it
- **Result:** -8.5% CAGR (27.2% vs 35.7%), WORSE drawdown (-54% vs -47%). Triggered 136/311 stock months (44%). Momentum stocks are volatile — they routinely dip 4% below last month's low then continue higher. Incompatible with the strategy's DNA.

### 5. Stop Loss on Entry Month Only (-4% Below Previous Month Low)
- **Test:** Apply the -4% stop only in the first month of a new entry, not on existing holdings
- **Result:** -1.7% CAGR (34.0% vs 35.7%), slightly worse DD (-48.7% vs -46.9%). Triggered 39 times. 85% of stops were "correct" (stock kept falling) but ONE missed recovery (PLTR +40.3% in Mar 2025) wiped out all savings from 39 good stops. Net negative because the avg stop saves only 0.3% but the avg false stop costs 10.4%.

### 6. Top 1 Stock (Buffer 1/5) with 1.8x Leverage
- **Test:** Hold only the #1 ranked stock with buffer 1/5
- **Result:** $7.9M (35x), 52% CAGR, -84% max DD. Catastrophically concentrated. Three bad years in a row at 1.8x (2018: -47%, 2019: -28%, 2021: -78%).

### 7. Top 5 Stocks (Buffer 5/10) with 1.8x Leverage
- **Test:** Hold top 5 with wider buffer
- **Result:** $29.6M (131x), 72% CAGR, -41% DD. Better DD than top 3 but 5x less return. The extra diversification from stocks #4-5 costs massively on upside.

### 8. 3x Leverage
- **Test:** 3x on all positions + gold
- **Result:** $4.2B, 176% CAGR, -73% max DD. Fantasy numbers (3x single-stock ETFs don't exist). Worst month -42.5%.

### 9. Tiered Gold Rotation (≥7 → 50/50, ≥9 → 100% gold)
- **Test:** Partial gold allocation in the 7-9 zone
- **Result:** $1.54B vs $1.50B — negligible difference (+0.1% CAGR). Not worth the execution complexity of maintaining two positions.

### 10. Previous Month Candle Size as Entry Filter
- **Test:** Filter entries based on previous month's candle range (high-to-low)
- **Result:** OPPOSITE of expected. Larger candles (30-50% range) have 79% win rate and +12.1% avg return. Smaller candles (10-15%) have 56% win rate. Big candles = strong trend = better entries. No useful filter.

## Underperformance Patterns (Known, Accepted)

These are structural costs of concentrated momentum. Cannot be filtered without destroying the edge.

| Pattern | Years | Cause |
|---------|-------|-------|
| Post-crash recovery lag | 2009, 2010 | Momentum selects defensives that held up; misses beaten-down tech recovery |
| Narrow mega-cap rally | 2019, 2023 | NDX driven by FAANG/Mag7; momentum picks mid-cap NDX names that lag |
| Gold rotation overstay | 2021, part of 2023 | NDX/XAUUSD stays above 7.0; gold flat while NDX rallies |
| Factor reversal | 2015, 2018 | Last year's winners flip to losers at macro regime changes |

## Key Design Decisions (Confirmed by 31-Year Backtest)
1. **Concentration wins:** Top 3 beats top 5/10/20 by wide margin at every leverage level
2. **Buffer 3/7 is optimal:** 3/3 too much churn, 3/10 similar to 3/7, wider adds no value
3. **Monthly rebalance:** Weekly too noisy, quarterly too slow
4. **12M/6M lookback is optimal:** Shorter is noisy, longer is too slow
5. **NSE vol adjustment works:** Battle-tested methodology
6. **NDX/XAUUSD ≥ 7.0 → gold** is the ONLY valid macro filter
7. **No stock-level stop losses work:** Momentum stocks are too volatile for price-based exits
8. **Buffer logic handles bad entries:** If a stock enters and immediately fails, it drops in rank and exits at next rebalance — no stop needed
9. **The strategy's edge comes from letting winners run through volatility**
10. **Bad years (8 of 31) are the structural cost of crushing in 18 of 31 years**

## Data Architecture
| File/Location | Purpose |
|------|---------|
| `historical-index-universe-data/prices/` | 480 Norgate OHLC CSVs (1982-2026) |
| `historical-index-universe-data/prices/$NDX__320.csv` | NASDAQ-100 index |
| `historical-index-universe-data/prices/XAUUSD__527909.csv` | Gold spot price |
| `historical-index-universe-data/prices/QQQ__145303.csv` | QQQ ETF (from 1999) |
| `historical-index-universe-data/universes/nasdaq100/membership_periods.csv` | SCD2 membership |
| `nasdaq_momentum/load_norgate_data.py` | Loads all Norgate data into DataFrames |
| `nasdaq_momentum/nasdaq100_daily_closes.csv` | Legacy yfinance data + leveraged ETFs |
| `nasdaq_momentum/leveraged_config.py` | Leveraged ETF ticker mapping |
| `nasdaq_momentum/backtest_wide_holdings.csv` | Full backtest output (378 months) |

## Scripts
| File | Purpose |
|------|---------|
| `backtest.py` | Main backtest engine (uses Norgate data, starts 1995) |
| `load_norgate_data.py` | Data loader for Norgate prices + SCD2 membership |
| `generate_html.py` | Generates interactive dashboard |
| `download_data.py` | yfinance download for leveraged ETFs |
| `leveraged_config.py` | Leveraged ETF ticker mapping |
| `nasdaq_momentum50_screener.py` | Screener for top 50 momentum |

## Current Holdings (July 2026)
- **Stocks:** MU, STX, WDC
- **Leveraged:** MUU, STX, WDC
- **NDX/XAUUSD ratio:** 7.56 (above 7.0 → in gold rotation currently)
- **Top 10 ranked:** SNDK, WDC, MU, STX, INTC, MRVL, LITE, AMAT, LRCX, ARM

## Future Enhancements (TODO)

### Volume Filter for SmallCap/MidCap Universes
- **Why:** Russell 2000, S&P SmallCap 600, and S&P MidCap 400 may select thinly-traded stocks that are hard to execute at backtested prices.
- **Implementation:** Add `min_avg_volume` config option (e.g., 500,000 shares/day minimum 20-day average). Filter out low-volume stocks before scoring.
- **Data needed:** Build `all_prices_volume.parquet` from Norgate CSVs (Volume column already exists in raw data).
- **Priority:** Low for NASDAQ-100 (all highly liquid). Required before deploying real money on smallcap/midcap strategies.
- **Not needed for:** NASDAQ-100, S&P 100, Russell Top 200, DJIA (all mega/large-cap, always liquid).

### VIX-Adaptive Lookback for Other Universes
- **Status:** Proven for NASDAQ-100 (41.3% CAGR vs 34.8% standard). Not yet tested for other universes.
- **TODO:** Test VIX>30 → 126d/42d lookback for S&P 500, Russell 1000, etc.

### Incremental Parquet Updates
- **Script:** `build_prices_parquet.py --incremental`
- **Monthly workflow:** Sync new CSVs from Windows VM → run incremental → re-run backtests
