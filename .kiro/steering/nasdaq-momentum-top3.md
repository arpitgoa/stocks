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

## Core Strategy Parameters (UPDATED July 2026)

### Stock Selection
- **Universe:** NASDAQ-100 constituents (point-in-time, SCD2 membership from Norgate)
- **Selection:** Top 3 stocks by Normalized Momentum Score
- **Entry buffer:** Stock must rank ≤ 3 to enter
- **Exit buffer:** Stock stays unless it drops below rank 7
- **Weighting:** Equal weight (~33% each), reset monthly
- **Rebalance:** Monthly (last trading day)
- **Gold Rotation:** If NDX/XAUUSD ≥ 6.8, hold 100% gold (XAUUSD)

### Momentum Score Calculation
1. **12M return** (skip last 5 trading days): Price(end) / Price(252 days ago) - 1
2. **6M return** (skip last 5 trading days): Price(end) / Price(126 days ago) - 1
3. **Volatility (σ):** Annualized std dev of daily log returns over 252 days
4. **Momentum Ratios:** MR_12 = 12M return / σ, MR_6 = 6M return / σ
5. **Z-Scores:** Z_12 = (MR_12 - mean) / std, Z_6 = (MR_6 - mean) / std
6. **Weighted Z:** VIX < 30: **70% × Z_12 + 30% × Z_6** | VIX > 30: **50% × Z_12 + 50% × Z_6**
7. **Normalized Score:** If Z ≥ 0 → (1+Z), else → (1-Z)⁻¹

### VIX-Adaptive Regime
| VIX Zone | Lookback | Z-Score Blend (12M/6M) |
|----------|----------|------------------------|
| < 30 (normal) | 252d / 126d | 70 / 30 |
| > 30 (panic) | 126d / 42d | 50 / 50 |

### Gold Rotation Signal
- **Ratio:** NDX index price / XAUUSD
- **Threshold:** ≥ 6.8 → hold 100% gold
- **Tested range:** 6.0-8.5; 6.8 is optimal (triggers slightly earlier than 7.0, catches dot-com protection)

### Per-Universe Config (`momentum_blend` in universe_config.py)
- Each universe has its own optimal blend: NASDAQ-100/Russell 1000/Top 200 use 70/30, SP500/others use 50/50
- `vix_momentum_blend` configures the VIX>30 fast-mode blend separately

### Results (1995–2026, 31.5 years, $100K + $1K/mo DCA)
- **XIRR:** 44.1%
- **Max Drawdown:** -26.8%
- **5-year rolling min CAGR:** +11.3%
- **10-year rolling min CAGR:** +17.5%
- **Win rate vs NDX:** 72% of years (23/32)

### Results Without DCA (Lump Sum $100K, Jan 2015 → Jul 2026)
- **CAGR:** 50.6%
- **Max DD:** -24.1%
- **Total return:** 11,016% (111x)

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

## Filters & Ideas TESTED AND REJECTED (July 2026 Comprehensive)

DO NOT re-test these. They have been thoroughly backtested and all make the strategy worse.

### Scoring & Blend Variations
| Test | Result |
|------|--------|
| 3-factor scoring (12M/9M/6M) | Worse — noise dilutes signal |
| 4-factor scoring (12M/9M/6M/3M) | Much worse |
| Acceleration bonus (3M Z-score) | -4.5% CAGR, worse DD |
| Vol penalty (penalize high-vol stocks) | -3.8% CAGR |
| Recent winner boost (1M return bonus) | -5.9% CAGR |
| Score-proportional weighting | -1.4% CAGR, worse DD |
| Inverse volatility weighting | -5.5% CAGR, worse DD |
| Conviction weighting (50/25/25) | -0.7% CAGR, worse DD |

### Buffer & Position Variations
| Test | Result |
|------|--------|
| Buffer 3/3 (no buffer) | -8% CAGR, -43% DD |
| Buffer 3/5 | -4% CAGR, -37% DD |
| Buffer 3/10 | -7% CAGR, -35% DD |
| Entry rank 2 vs 3 vs 4 | No difference (all produce same portfolio) |
| Hold 2 stocks | -8% CAGR, -42% DD |
| Hold 4 stocks | -7% CAGR, -40% DD |
| Hold 5 stocks | -12% CAGR, -46% DD |

### Timing & Rebalance Variations
| Test | Result |
|------|--------|
| 6-month rebalance | -30% CAGR, -69% DD (destroys risk management) |
| Drift weights (only reset semi-annually) | No difference from monthly equal weight |
| Delayed entry (wait 1-5 days after big month) | All worse or same |
| Entry at mid-month | Worse (misses first-day move) |

### Stop Losses & Intra-Month Trading
| Test | Result |
|------|--------|
| 3% stop loss with 3 re-entries | -18% CAGR, -50% DD (death by 1000 cuts) |
| 5% stop loss | -8% CAGR |
| Mid-month exit if stock down >7% | -6% CAGR |
| Tournament: enter 5, keep best 3 after 5 days | -13% CAGR (first-week winners mean-revert) |
| Tournament: 3→1 (keep only best after 5d) | -9% CAGR |
| Drop worst after 3d, replace with #4 | -4% CAGR, much worse DD |

### Rate of Change / Momentum of Momentum
| Test | Result |
|------|--------|
| Pure ROC (rank by score % change) | -23% CAGR |
| Blended: 90% score + 10% ROC | -4.4% CAGR |
| Top 10 → pick 3 by ROC within | -18% CAGR |
| ROC filter (only pick improving stocks) | -11% CAGR |
| Decay exit (kick stocks with falling scores) | -4 to -14% CAGR |

### Volume-Based Signals
| Test | Result |
|------|--------|
| Individual stock up/down volume ratio | No predictive power within top 10 (winners = losers on every metric) |
| Stock volume vs 3M/6M average | No signal |
| QQQ volume regime (high vs low) | Marginal difference, not exploitable |
| Volume as entry filter or boost | All worse |

### Macro Overlays
| Test | Result |
|------|--------|
| NDX below 10-month MA → gold | -10% CAGR, worse DD |
| NDX trend sizing (reduce when < 50MA) | -5% CAGR |
| Calendar month filter (skip July/September) | -4 to -8% CAGR |
| Realized vol switch (NDX vol > 30%) | Same or worse |
| VIX < 15 → reduce exposure | -2% CAGR |
| Breadth-based hedging (hold gold when broad market) | -2 to -5% CAGR |

### Stock Selection Filters
| Test | Result |
|------|--------|
| Absolute momentum filter (12M > 0) | -1.2% CAGR, worse DD |
| 12M return cap (exclude >200% gainers) | -17% CAGR (kills the engine) |
| Relative strength vs NDX filter | -8% CAGR |
| Trend filter (stock must be > 50MA) | -12% CAGR |
| Anti-correlation diversification | -7% CAGR, -51% DD |
| Breakout swap (rank 4-10 with high 1M into portfolio) | -2 to -10% CAGR |

### Why the 198% Ceiling Can't Be Reached with Price Data
- Winners and losers within top 10 are **statistically identical** on: candle size, volume ratio, volatility, distance from high, 5d/10d momentum, gap frequency, close position in range, up/down volume ratio
- The difference is driven by **future unpredictable events**: earnings surprises, analyst revisions, news, sector rotation, institutional flow
- To close the gap, would need: earnings revision data, options flow, insider buying, or ML on fundamentals

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
2. **Buffer 3/7 is optimal:** 3/3 too much churn (-43% DD), 3/5 too tight, 3/10 too wide
3. **Monthly rebalance:** Weekly too noisy, 6-monthly destroys risk management (-69% DD)
4. **70/30 blend is optimal for calm markets:** Favors sustained 12M trend, avoids whipsaw
5. **50/50 blend for VIX>30:** More responsive during panic to catch rotation
6. **NSE vol adjustment works:** Battle-tested methodology
7. **NDX/XAUUSD ≥ 6.8 → gold** is the ONLY valid macro filter
8. **Skip 5 trading days is exactly optimal:** Not 3, not 7 — precise sweet spot
9. **3 stocks is the magic number:** 2 stocks too volatile, 4-5 stocks too diluted
10. **Equal weight beats all alternatives** (conviction weighting, score-proportional, inverse vol)
11. **No stock-level stop losses work:** Momentum stocks are too volatile for price-based exits
12. **Buffer logic handles bad entries:** If a stock enters and immediately fails, it drops in rank and exits at next rebalance
13. **Bad years (8-9 of 32) are the structural cost of crushing in 23 of 32 years**

## Optimization Research (July 2026 — Comprehensive)

### What Improved the Strategy (IMPLEMENTED)
| Change | Impact | Implemented |
|--------|--------|-------------|
| 70/30 Z-score blend (from 50/50) | +2.7% CAGR, -5.8% DD | ✅ |
| Gold threshold 6.8 (from 7.0) | +1.5% CAGR, same DD | ✅ |
| Per-universe `momentum_blend` config | Each universe at its optimal | ✅ |
| SP500 buffer 10/15 (from 10/20) | +0.9% CAGR, same DD | ✅ |
| yfinance→Norgate column rename fix | Data pipeline fix | ✅ |
| Weekend/current-day download skip | Rate limit protection | ✅ |
| Dynamic "Top N" label in dashboard | Fixes misleading "Top 7" | ✅ |

### Theoretical Maximum (Perfect Hindsight Analysis)
- **Best 3 out of top 10 (backward-looking):** 198.7% CAGR, -13.7% DD
- **Our picks (top 3 by score):** ~44% CAGR
- **Random 3 from top 10:** 25.1% CAGR
- **Worst 3 from top 10:** -1.9% CAGR
- **Conclusion:** Scoring correctly identifies the top-10 pool (huge value vs random). Within-top-10 selection is driven by unpredictable future events (earnings, news, flow). No observable price/volume characteristic at entry differentiates winners from losers within the top 10.

### Saved for Future Consideration (Not Implemented)
| Idea | Result | Why Not |
|------|--------|---------|
| Hybrid gold signal (MA-trend + crash trigger) | 49-50% CAGR, -27.5% DD | Backward-looking, fit to 3 events. Risk of -40% DD if 2000-like event occurs with rising ratio |
| Drop worst stock after 3 days | 46.8% CAGR, -37% DD | +1.4% CAGR but +10% worse DD — not worth the tradeoff |
| Breadth-based hedging | Insight valid, not exploitable | Narrow breadth = +5.4%/mo vs broad = +3.8%/mo, but hedging during broad costs more than it saves |

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

## Scripts (Current Architecture)
| File | Purpose |
|------|---------|
| `run_backtest.py` | CLI wrapper — runs backtest for any universe |
| `live_signal.py` | Updates prices from yfinance + generates live signals for all universes |
| `generate_dashboard.py` | Generates interactive HTML dashboard from backtest CSV |
| `universe_config.py` | All universe parameters (top_n, buffer, gold, blend) |
| `leveraged_config.py` | Leveraged ETF ticker mapping |
| `dashboard_template.py` | HTML template for dashboards |
| `core/engine.py` | Main backtest loop (gold, VIX, buffer, scoring) |
| `core/momentum.py` | Momentum scoring (Z-scores, normalization, precomputed cache) |
| `core/data_loader.py` | Loads prices from parquet/CSV + membership |
| `core/metrics.py` | XIRR, max drawdown calculations |
| `scripts/test_strategy.py` | Parameter sweep testing tool with rolling returns |
| `scripts/build_prices_parquet.py` | Builds all_prices.parquet from Norgate CSVs |
| `scripts/build_comparison_dashboard.py` | ETF comparison dashboard |
| `github_action/generate_signals.py` | GitHub Actions signal pipeline |
| `github_action/send_telegram.py` | Telegram notification |

## Key Commands
```bash
# Run full refresh (update prices + all backtests + all dashboards)
python live_signal.py --all --dashboard

# Run single universe backtest
python run_backtest.py --universe nasdaq100_vix --dashboard

# Test parameters before committing
python scripts/test_strategy.py --universe nasdaq100_vix
python scripts/test_strategy.py --universe nasdaq100_vix --period 2015-2026

# List all universes
python run_backtest.py --list
```

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
