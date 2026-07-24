"""
Universe Configuration for Momentum Strategy
=============================================
Defines parameters for each universe: stock selection, buffer, and gold rotation.

Gold rotation uses NDX/XAUUSD as the universal signal for all universes.
Rationale: NDX is the most momentum-sensitive major index. When NDX is expensive
vs gold, the broad market is in risk-on mode and concentrated momentum is risky.
The threshold can be tuned per-universe if universe-specific index data becomes available.

TODO: Add $SPX, $RUI, $DJI price data from Norgate to test universe-specific
      gold thresholds (e.g., SPX/XAUUSD for S&P 500 universe).
"""

# ============================================================
# UNIVERSE CONFIGURATIONS
# ============================================================

UNIVERSE_CONFIGS = {
    # --- NASDAQ Family ---
    "nasdaq100": {
        "label": "NASDAQ-100",
        "folder": "nasdaq100",
        "start_year": 1995,
        "benchmark": "$NDX",
        "benchmark_etf": "QQQ",
        "top_n": 3,
        "entry_rank": 3,
        "exit_rank": 7,
        "gold_signal_index": "$NDX",
        "gold_threshold": 7.0,
        "momentum_blend": (0.7, 0.3),
        "notes": "Core strategy. 34.8% XIRR over 31 years. Best risk/reward.",
    },
    "nasdaq100_vix": {
        "label": "NASDAQ-100 VIX Optimized",
        "folder": "nasdaq100",
        "start_year": 1995,
        "benchmark": "$NDX",
        "benchmark_etf": "QQQ",
        "top_n": 3,
        "entry_rank": 3,
        "exit_rank": 7,
        "gold_signal_index": "$NDX",
        "gold_threshold": 6.8,
        "vix_threshold": 30,
        "vix_fast_long": 126,
        "vix_fast_short": 42,
        "momentum_blend": (0.7, 0.3),
        "vix_momentum_blend": (0.5, 0.5),
        "notes": "VIX>30 switches to 126d/42d lookback with 50/50 blend. Default 70/30 blend. Gold at 6.8. 44.1% XIRR, -26.8% DD.",
    },
    "nasdaq_q50": {
        "label": "NASDAQ Q-50 (ranks 101-150)",
        "folder": "nasdaq_q50",
        "start_year": 2008,
        "benchmark": "$NXTQ",
        "benchmark_etf": "QQQ",
        "top_n": 3,
        "entry_rank": 3,
        "exit_rank": 7,
        "gold_signal_index": "$NDX",
        "gold_threshold": 7.0,
        "momentum_blend": (0.7, 0.3),
        "notes": "Mid-cap NASDAQ. Uses NDX for gold signal (same ecosystem).",
    },
    "nasdaq_biotech": {
        "label": "NASDAQ Biotech",
        "folder": "nasdaq_biotech",
        "start_year": 2002,
        "benchmark": "$NBI",
        "benchmark_etf": "QQQ",
        "top_n": 3,
        "entry_rank": 3,
        "exit_rank": 7,
        "gold_signal_index": "$NBI",
        "gold_threshold": 3.5,
        "momentum_blend": (0.5, 0.5),
        "notes": "Sector-specific. Uses NBI/XAUUSD for gold signal.",
    },

    # --- S&P Family ---
    "sp500": {
        "label": "S&P 500",
        "folder": "sp500",
        "start_year": 1990,
        "benchmark": "$SPX",
        "benchmark_etf": "SPY",
        "top_n": 10,
        "entry_rank": 10,
        "exit_rank": 15,
        "gold_signal_index": "$SPX",
        "gold_threshold": 2.2,
        "momentum_blend": (0.5, 0.5),
        "notes": "Optimized: top 10, 10/15 buffer, 50/50 blend. 18.9% CAGR, -35% DD.",
    },
    "sp100": {
        "label": "S&P 100",
        "folder": "sp100",
        "start_year": 1990,
        "benchmark": "$OEX",
        "benchmark_etf": "SPY",
        "top_n": 3,
        "entry_rank": 3,
        "exit_rank": 7,
        "gold_signal_index": "$OEX",
        "gold_threshold": 1.0,
        "momentum_blend": (0.5, 0.5),
        "notes": "Mega-caps. Optimized: 3/7, OEX/XAUUSD >= 1.0. 18.5% XIRR.",
    },
    "sp_midcap400": {
        "label": "S&P MidCap 400",
        "folder": "sp_midcap400",
        "start_year": 1992,
        "benchmark": "$MID",
        "benchmark_etf": "MDY",
        "top_n": 5,
        "entry_rank": 5,
        "exit_rank": 10,
        "gold_signal_index": "$MID",
        "gold_threshold": 1.5,
        "momentum_blend": (0.5, 0.5),
        "notes": "Mid-caps. Optimized: 5/10, MID/XAUUSD >= 1.5. 22.4% XIRR.",
    },
    "sp_smallcap600": {
        "label": "S&P SmallCap 600",
        "folder": "sp_smallcap600",
        "start_year": 1995,
        "benchmark": "$SML",
        "benchmark_etf": "IJR",
        "top_n": 10,
        "entry_rank": 10,
        "exit_rank": 20,
        "gold_signal_index": "$SML",
        "gold_threshold": 0.7,
        "momentum_blend": (0.5, 0.5),
        "notes": "Small-caps. Optimized: SML/XAUUSD >= 0.7. 16.8% XIRR.",
    },

    # --- Russell Family ---
    "russell1000": {
        "label": "Russell 1000",
        "folder": "russell1000",
        "start_year": 1991,
        "benchmark": "$RUI",
        "benchmark_etf": "IWB",
        "top_n": 3,
        "entry_rank": 3,
        "exit_rank": 7,
        "gold_signal_index": "$RUI",
        "gold_threshold": 2.4,
        "momentum_blend": (0.7, 0.3),
        "notes": "Large-cap broad. Optimized: 3/7 beats 10/20. 26.3% XIRR.",
    },
    "russell2000": {
        "label": "Russell 2000",
        "folder": "russell2000",
        "start_year": 1991,
        "benchmark": "$RUT",
        "benchmark_etf": "IWM",
        "top_n": 10,
        "entry_rank": 10,
        "exit_rank": 25,
        "gold_signal_index": "$RUT",
        "gold_threshold": 1.6,
        "momentum_blend": (0.5, 0.5),
        "notes": "Small-caps. RUT/XAUUSD >= 1.6 for gold.",
    },
    "russell_midcap": {
        "label": "Russell Mid Cap",
        "folder": "russell_midcap",
        "start_year": 1996,
        "benchmark": "$RMC",
        "benchmark_etf": "IWR",
        "top_n": 10,
        "entry_rank": 10,
        "exit_rank": 20,
        "gold_signal_index": "$RMC",
        "gold_threshold": 1.0,
        "momentum_blend": (0.5, 0.5),
        "notes": "Mid-cap. Optimized: RMC/XAUUSD >= 1.0. Best DD (-22.9%).",
    },
    "russell_top200": {
        "label": "Russell Top 200",
        "folder": "russell_top200",
        "start_year": 1996,
        "benchmark": "$RT200",
        "benchmark_etf": "IWL",
        "top_n": 3,
        "entry_rank": 3,
        "exit_rank": 7,
        "gold_signal_index": "$RT200",
        "gold_threshold": 1.2,
        "momentum_blend": (0.7, 0.3),
        "notes": "Mega-caps. Optimized: 3/7. 21.0% XIRR, -35.3% DD.",
    },

    # --- Other ---
    "djia": {
        "label": "Dow Jones Industrial Average",
        "folder": "djia",
        "start_year": 1991,
        "benchmark": "$DJI",
        "benchmark_etf": "DIA",
        "top_n": 3,
        "entry_rank": 3,
        "exit_rank": 7,
        "gold_signal_index": "$DJI",
        "gold_threshold": 18.0,
        "momentum_blend": (0.5, 0.5),
        "notes": "Only 30 stocks. Optimized: DJI/XAUUSD >= 18. 14.3% XIRR, -24.9% DD.",
    },
}


# ============================================================
# HELPER
# ============================================================

def get_config(universe_name):
    """Get configuration for a universe. Raises KeyError if not found."""
    if universe_name not in UNIVERSE_CONFIGS:
        available = ", ".join(sorted(UNIVERSE_CONFIGS.keys()))
        raise KeyError(f"Unknown universe '{universe_name}'. Available: {available}")
    return UNIVERSE_CONFIGS[universe_name]


def list_universes():
    """Print all available universes with their parameters."""
    print(f"{'Universe':<20} {'Label':<30} {'Top N':>5} {'Buffer':>8} {'Start':>6} {'Gold':>5}")
    print("-" * 80)
    for name, cfg in sorted(UNIVERSE_CONFIGS.items()):
        buffer = f"{cfg['entry_rank']}/{cfg['exit_rank']}"
        print(f"{name:<20} {cfg['label']:<30} {cfg['top_n']:>5} {buffer:>8} {cfg['start_year']:>6} {cfg['gold_threshold']:>5.1f}")


if __name__ == "__main__":
    list_universes()
