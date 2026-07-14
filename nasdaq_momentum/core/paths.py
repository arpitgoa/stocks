"""
Centralized path configuration.
All paths used across the system are defined here.
"""

from pathlib import Path

# Root directories
NORGATE_DIR = Path.home() / "Documents" / "workspace" / "historical-index-universe-data"
PRICES_DIR = NORGATE_DIR / "prices"
UNIVERSES_DIR = NORGATE_DIR / "universes"
OUTPUT_DIR = Path.home() / "Documents" / "workspace" / "stocks" / "nasdaq_momentum"

# Data files
DATA_DIR = OUTPUT_DIR / "data"
PRICES_PARQUET = DATA_DIR / "all_prices.parquet"
PRECOMPUTED_MOMENTUM_PARQUET = DATA_DIR / "precomputed_momentum.parquet"
LEGACY_CLOSES_CSV = DATA_DIR / "nasdaq100_daily_closes.csv"

# Dashboard output
DASHBOARDS_DIR = OUTPUT_DIR / "dashboards"
