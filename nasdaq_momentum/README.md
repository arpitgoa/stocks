# Momentum Strategy Backtest System

A production-grade momentum backtest engine covering 13 stock market universes from 1990–2026.
Uses point-in-time membership data (survivorship-bias-free), monthly rebalancing with buffer logic,
gold rotation for downside protection, and optional VIX-adaptive lookback periods.

**Primary universe:** NASDAQ-100 Top 3 → 34.8% XIRR over 31 years (1995–2026).

---

## Quick Start

```bash
# List all available universes and their parameters
python run_backtest.py --list

# Run backtest for one universe
python run_backtest.py --universe nasdaq100

# Run backtest and generate interactive HTML dashboard
python run_backtest.py --universe nasdaq100 --dashboard

# Run all 13 universes with dashboards
python run_backtest.py --all --dashboard

# Regenerate all dashboards from existing CSV data (no re-running backtest)
python generate_dashboard.py --all

# Override parameters for experimentation
python run_backtest.py --universe sp500 --top-n 5 --exit-rank 10 --gold-threshold 3.0
```

---

## Strategy Summary

### How It Works (Monthly)

1. **Check Gold Rotation Signal** — If `IndexPrice / GoldPrice ≥ threshold`, hold 100% gold (XAUUSD) for the month. Skip stock selection.
2. **Score All Universe Members** — Calculate Normalized Momentum Score for every stock currently in the index (point-in-time membership).
3. **Apply Buffer Logic** — Existing holdings stay unless they fall below exit rank. New entries only if ranked within entry rank. Fill remaining slots from top-ranked.
4. **Hold for 1 Month** — Equal-weight the selected stocks. Measure returns until next rebalance.
5. **Track Leveraged Returns** — If a 2x single-stock ETF exists (e.g., NVDL for NVDA), track what leveraged returns would have been.

### Momentum Score Calculation (NSE Methodology)

```
1. 12-month return (skip last 5 days): Price(end) / Price(252d ago) - 1
2. 6-month return (skip last 5 days):  Price(end) / Price(126d ago) - 1
3. Annualized volatility: StdDev(daily log returns over 252d) × √252
4. MR_12 = 12M_return / volatility
5. MR_6  = 6M_return / volatility
6. Z_12  = (MR_12 - mean(all MR_12)) / std(all MR_12)
7. Z_6   = (MR_6  - mean(all MR_6))  / std(all MR_6)
8. Weighted_Z = 0.5 × Z_12 + 0.5 × Z_6
9. Score = (1 + Z) if Z ≥ 0, else 1/(1 - Z)
```

The 5-day skip avoids short-term mean reversion. Volatility normalization prevents high-beta stocks from dominating purely on leverage.

---

## Project Structure

```
nasdaq_momentum/
│
├── run_backtest.py            # CLI entry point for running backtests
├── generate_dashboard.py      # CLI entry point for generating HTML dashboards
├── universe_config.py         # All universe definitions (13 universes)
├── leveraged_config.py        # Stock → 2x leveraged ETF ticker mapping
├── dashboard_template.py      # HTML/JS template (inline, single-file dashboards)
├── README.md                  # This file
│
├── core/                      # Core engine (importable as `from core import ...`)
│   ├── __init__.py            # Public API: run_backtest, xirr, max_drawdown, etc.
│   ├── paths.py               # All file/directory path constants
│   ├── data_loader.py         # Load prices from parquet/CSV + membership data
│   ├── momentum.py            # Momentum scoring (precomputed + live calculation)
│   ├── engine.py              # Main backtest loop, buffer logic, gold rotation
│   └── metrics.py             # XIRR and max drawdown calculations
│
├── scripts/                   # Data pipeline scripts (run manually)
│   ├── build_prices_parquet.py       # Build all_prices.parquet from Norgate CSVs
│   ├── precompute_scores.py          # Precompute momentum ratios for speed
│   ├── download_data.py              # Download leveraged ETF data via yfinance
│   ├── load_norgate_data.py          # Utility to load Norgate data into DataFrames
│   └── nasdaq100_historical_changes.py  # Parse NASDAQ-100 index changes
│
├── tools/                     # One-off utilities and scrapers
│   ├── nasdaq_momentum50_screener.py  # Live screener (runs against current market)
│   ├── download_on_page.js            # Browser console script for bulk downloads
│   └── investing_com_downloader.js    # Investing.com data scraper
│
├── data/                      # Generated data files (large, .gitignore'd)
│   ├── all_prices.parquet             # 20K+ tickers × 30+ years of daily closes
│   ├── precomputed_momentum.parquet   # Pre-calculated MR_12/MR_6 for all dates
│   ├── nasdaq100_daily_closes.csv     # Legacy yfinance data + leveraged ETFs
│   └── qqq_daily_closes.csv           # QQQ ETF prices
│
├── dashboards/                # Generated HTML output
│   ├── index.html             # Landing page — all universes, heatmap, charts
│   ├── nasdaq100/             # Each universe gets its own folder
│   │   ├── backtest_wide.csv  # Monthly returns data (consumed by dashboard)
│   │   └── dashboard.html     # Interactive single-file HTML dashboard
│   ├── nasdaq100_vix/
│   ├── sp500/
│   ├── sp100/
│   ├── sp_midcap400/
│   ├── sp_smallcap600/
│   ├── russell1000/
│   ├── russell2000/
│   ├── russell_midcap/
│   ├── russell_top200/
│   ├── djia/
│   ├── nasdaq_q50/
│   └── nasdaq_biotech/
│
└── _legacy/                   # Archived old code (not used, kept for reference)
```

---

## File-by-File Documentation

### Root Entry Points

| File | Purpose |
|------|---------|
| `run_backtest.py` | CLI wrapper. Parses arguments (--universe, --all, --top-n, etc.) and calls `core.engine.run_backtest()`. Can also trigger dashboard generation with `--dashboard`. |
| `generate_dashboard.py` | Reads `backtest_wide.csv` for a universe, loads bench ticker prices from Norgate CSVs, builds a self-contained HTML dashboard from `dashboard_template.py`. |
| `universe_config.py` | Dictionary of all 13 universe configurations: stock count (top_n), buffer (entry/exit rank), gold rotation threshold, benchmark symbol, start year, and notes. This is the single source of truth for strategy parameters. |
| `leveraged_config.py` | Maps 22 stock tickers to their 2x leveraged single-stock ETFs (e.g., NVDA→NVDL, TSLA→TSLL). Used to show "what if you used leverage" in dashboards. Only tracks returns when the actual ETF exists (no synthetic leverage). |
| `dashboard_template.py` | Contains two Python string constants (`TEMPLATE_BEFORE`, `TEMPLATE_AFTER`) that form the HTML/CSS/JS of each dashboard. The JSON data gets sandwiched between them. Includes: cumulative growth chart, annual returns bar chart, stock stats table, monthly detail table, return distribution histogram. |

### `core/` — Engine Modules

| File | Lines | Purpose |
|------|-------|---------|
| `paths.py` | 20 | Defines all directory and file paths. Single place to update if directories move. |
| `data_loader.py` | 120 | `load_all_prices()` — loads the parquet (cached). `load_prices_for_universe()` — filters to relevant tickers. `load_membership()` — reads SCD2 membership CSV. `build_membership_lookup()` — pre-builds {date → [tickers]} dict for O(1) lookup. |
| `momentum.py` | 200 | `calculate_momentum_scores()` — primary API. Uses precomputed parquet if available (O(1) date lookup), falls back to live calculation from prices. `score_with_custom_lookback()` — used when VIX > 30 to switch to faster 126d/42d lookback. Normalization (Z-scores → final score) is shared. |
| `engine.py` | 340 | `run_backtest()` — orchestrates the full monthly loop. Internal helpers: `_check_gold_rotation()`, `_apply_buffer_logic()`, `_calculate_period_returns()`, `_save_wide_csv()`. Produces both the portfolio value and the `backtest_wide.csv` file consumed by dashboards. |
| `metrics.py` | 55 | `xirr(cashflows)` — solves for IRR with irregular dates using Brent's method. `max_drawdown(values)` — single-pass peak-to-trough calculation returning (fraction, peak_idx, trough_idx). |

### `scripts/` — Data Pipeline

| File | Purpose | When to Run |
|------|---------|-------------|
| `build_prices_parquet.py` | Reads all individual Norgate CSV files (20K+) and consolidates into a single `data/all_prices.parquet`. Supports `--incremental` to only add new dates/tickers without full rebuild. | After syncing new Norgate data from Windows VM. |
| `precompute_scores.py` | Calculates MR_12 and MR_6 for every ticker on every month-end date, saves to `data/precomputed_momentum.parquet`. Makes backtests ~5x faster by avoiding per-ticker price slicing. Has `--verify` flag to confirm precomputed matches live calculation. | After `build_prices_parquet.py`. Optional but recommended. |
| `download_data.py` | Uses yfinance to download daily prices for 258 historical NASDAQ-100 tickers + leveraged ETFs. Saves to `data/nasdaq100_daily_closes.csv`. | Only needed for leveraged ETF data not in Norgate. |
| `load_norgate_data.py` | Utility module with `load_prices()` and `get_members_at_date()`. Originally the primary data loader before parquet was built. Still usable standalone. | Imported by legacy code. |
| `nasdaq100_historical_changes.py` | Parses NASDAQ-100 index addition/removal history to build membership timelines. | One-off, already done. |

### `tools/` — Utilities

| File | Purpose |
|------|---------|
| `nasdaq_momentum50_screener.py` | Live screener that pulls current NASDAQ-100 prices from yfinance, calculates momentum scores, and ranks top 50 stocks. Use for monthly rebalancing decisions. |
| `download_on_page.js` | Browser console script to bulk-download data from financial websites. |
| `investing_com_downloader.js` | Investing.com-specific JavaScript scraper for historical data. |

### `data/` — Generated Files

| File | Size | Content |
|------|------|---------|
| `all_prices.parquet` | ~280 MB | Daily Close prices for 20K+ tickers (1896–2026). Date index × ticker columns. The main data source for all backtests. |
| `precomputed_momentum.parquet` | ~150 MB | Pre-calculated MR_12 and MR_6 for every ticker on every month-end. 5.8M rows. |
| `nasdaq100_daily_closes.csv` | ~15 MB | Legacy yfinance prices + leveraged ETF data (NVDL, TSLL, etc.). Used as fallback for leveraged return tracking. |
| `qqq_daily_closes.csv` | ~1 MB | QQQ ETF daily prices. Legacy file. |

### `dashboards/` — Output

Each universe folder contains:
- `backtest_wide.csv` — Monthly returns data with all holdings, benchmark, leverage, VIX, top 10 ranked.
- `dashboard.html` — Self-contained interactive dashboard (Chart.js, no external dependencies).

The `index.html` landing page shows all universes with:
- Performance cards (CAGR, alpha, drawdown, multiple)
- Cumulative growth line chart (log scale, all universes)
- Annual returns heatmap (color-coded, all years × all universes)

---

## Universe Configurations

| Universe | Stocks | Buffer | Gold Signal | Start | XIRR |
|----------|--------|--------|-------------|-------|------|
| NASDAQ-100 | Top 3 | 3/7 | NDX/XAUUSD ≥ 7.0 | 1995 | 34.8% |
| NASDAQ-100 VIX | Top 3 | 3/7 | NDX/XAUUSD ≥ 7.0 + VIX>30 fast | 1995 | 41.3% |
| Russell 1000 | Top 3 | 3/7 | RUI/XAUUSD ≥ 2.4 | 1991 | 26.3% |
| S&P MidCap 400 | Top 5 | 5/10 | MID/XAUUSD ≥ 1.5 | 1992 | 22.4% |
| NASDAQ Q-50 | Top 3 | 3/7 | NDX/XAUUSD ≥ 7.0 | 2008 | 21.7% |
| Russell Top 200 | Top 3 | 3/7 | RT200/XAUUSD ≥ 1.2 | 1996 | 21.0% |
| S&P 500 | Top 3 | 3/7 | SPX/XAUUSD ≥ 2.2 | 1990 | 18.9% |
| S&P 100 | Top 3 | 3/7 | OEX/XAUUSD ≥ 1.0 | 1990 | 18.5% |
| Russell 2000 | Top 10 | 10/25 | RUT/XAUUSD ≥ 1.6 | 1991 | 17.2% |
| S&P SmallCap 600 | Top 10 | 10/20 | SML/XAUUSD ≥ 0.7 | 1995 | 16.8% |
| Russell Mid Cap | Top 10 | 10/20 | RMC/XAUUSD ≥ 1.0 | 1996 | 16.0% |
| DJIA | Top 3 | 3/7 | DJI/XAUUSD ≥ 18 | 1991 | 14.3% |
| NASDAQ Biotech | Top 3 | 3/7 | NBI/XAUUSD ≥ 3.5 | 2002 | 13.5% |

---

## Data Sources

| Source | What | Location |
|--------|------|----------|
| **Norgate Data** (professional, paid) | Daily OHLCV for 20K+ tickers back to 1980s. Survivorship-bias-free. Includes delisted stocks, indices, gold. | `~/Documents/workspace/historical-index-universe-data/prices/` |
| **Norgate Membership** | SCD2 (start/end date) for which stocks were in each index at any point in time. | `~/Documents/workspace/historical-index-universe-data/universes/{index}/membership_periods.csv` |
| **yfinance** | Leveraged ETF prices (NVDL, TSLL, etc.) — Norgate doesn't carry these. | `data/nasdaq100_daily_closes.csv` |
| **CBOE** | VIX historical data. | Included in the parquet. |

Norgate data is exported on a Windows VM and synced via git (membership CSVs) + manual file transfer (prices folder — 8.5GB, too large for GitHub).

---

## Data Pipeline Workflow

Run this monthly after syncing new Norgate data:

```bash
# Step 1: Build/update the consolidated parquet
python scripts/build_prices_parquet.py --incremental

# Step 2: Precompute momentum scores (speeds up backtests 5x)
python scripts/precompute_scores.py

# Step 3: Run all backtests and generate dashboards
python run_backtest.py --all --dashboard

# Step 4: Download latest leveraged ETF prices (optional)
python scripts/download_data.py
```

---

## Key Design Decisions

1. **Parquet over individual CSVs** — Loading 3000 CSVs takes 45 seconds. One parquet takes 2 seconds.
2. **Precomputed momentum scores** — Computing MR_12/MR_6 for thousands of tickers × hundreds of dates is expensive. Precomputing makes repeated backtests instant.
3. **Buffer logic** — Prevents excessive turnover. A stock only enters at rank ≤ 3 and only exits when it drops below rank 7. This keeps winners running.
4. **Gold rotation** — Universal downside protection. Uses Index/XAUUSD ratio — when stocks are expensive relative to gold, the market is overheated.
5. **Point-in-time membership** — Uses SCD2 (exact entry/exit dates) from Norgate. No survivorship bias. Tested with stocks that were delisted (Enron, Worldcom, etc.).
6. **Per-universe gold thresholds** — Each index has different absolute price levels vs gold. Thresholds optimized individually.
7. **Single-file dashboards** — Each HTML dashboard is completely self-contained (inline data, inline JS/CSS). No web server needed. Just open in browser.

---

## Interpreting the Dashboard

Each dashboard shows:

- **Summary cards** — Period, final value, CAGR, max drawdown, best/worst months, win/lose streaks, next month's holdings.
- **Cumulative chart** — Strategy vs Leverage vs Benchmark vs Invested (log scale).
- **Annual returns bar chart** — Year-by-year comparison (grouped by calendar year the return was realized).
- **Stock stats table** — Every stock ever held, sorted by P&L. Shows avg return/month, max gain/loss, months held, longest streak.
- **Monthly detail table** — Every month: returns, VIX, holdings with individual returns, non-held bench stocks, swaps.
- **Return distribution** — Histogram of all individual stock-month returns.

---

## Notes for Real Money Deployment

- The **NASDAQ-100 VIX Optimized** variant (41.3% CAGR) uses VIX > 30 → switch to 126d/42d lookback. This is more responsive during crashes.
- **Leveraged returns** only show actual 2x ETF returns when the ETF existed. No synthetic leverage is applied.
- The `tools/nasdaq_momentum50_screener.py` can be used for monthly rebalancing signals.
- Volume filtering (TODO) is needed before deploying on smallcap/midcap universes to avoid illiquid stocks.
