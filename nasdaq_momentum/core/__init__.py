"""
Core modules for the Momentum Backtest System
==============================================
Organized structure:
  - data_loader: Load prices (parquet/CSV) and membership data
  - momentum: Momentum scoring algorithms (vectorized + VIX-adaptive)
  - engine: Main backtest loop with buffer logic and gold rotation
  - metrics: XIRR, drawdown, and summary calculations
  - paths: Centralized path configuration
"""

from .paths import NORGATE_DIR, PRICES_DIR, UNIVERSES_DIR, OUTPUT_DIR, PRICES_PARQUET, DATA_DIR
from .data_loader import load_prices_for_universe, load_membership, build_membership_lookup
from .momentum import calculate_momentum_scores, score_with_custom_lookback
from .engine import run_backtest
from .metrics import xirr, max_drawdown
