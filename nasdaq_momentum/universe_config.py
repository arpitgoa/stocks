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
        "notes": "Core strategy. 33.8% XIRR over 31 years. Best risk/reward.",
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
        "notes": "Sector-specific. Uses NBI/XAUUSD for gold signal.",
    },

    # --- S&P Family ---
    "sp500": {
        "label": "S&P 500",
        "folder": "sp500",
        "start_year": 1990,
        "benchmark": "$SPX",
        "benchmark_etf": "SPY",
        "top_n": 20,
        "entry_rank": 20,
        "exit_rank": 40,
        "gold_signal_index": "$SPX",
        "gold_threshold": 4.6,
        "notes": "Broader universe (500 stocks). SPX/XAUUSD >= 4.6 for gold.",
    },
    "sp100": {
        "label": "S&P 100",
        "folder": "sp100",
        "start_year": 1990,
        "benchmark": "$OEX",
        "benchmark_etf": "SPY",
        "top_n": 5,
        "entry_rank": 5,
        "exit_rank": 12,
        "gold_signal_index": "$OEX",
        "gold_threshold": 2.4,
        "notes": "Mega-caps only. OEX/XAUUSD >= 2.4 for gold.",
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
        "gold_threshold": 1.9,
        "notes": "Mid-caps. MID/XAUUSD >= 1.9 for gold. Optimized: 5/10 beats 10/20.",
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
        "gold_threshold": 1.0,
        "notes": "Small-caps. SML/XAUUSD >= 1.0 for gold.",
    },

    # --- Russell Family ---
    "russell1000": {
        "label": "Russell 1000",
        "folder": "russell1000",
        "start_year": 1991,
        "benchmark": "$RUI",
        "benchmark_etf": "IWB",
        "top_n": 10,
        "entry_rank": 10,
        "exit_rank": 20,
        "gold_signal_index": "$RUI",
        "gold_threshold": 2.4,
        "notes": "Large-cap broad. RUI/XAUUSD >= 2.4 for gold.",
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
        "gold_threshold": 2.0,
        "notes": "Mid-cap sweet spot. RMC/XAUUSD >= 2.0 for gold.",
    },
    "russell_top200": {
        "label": "Russell Top 200",
        "folder": "russell_top200",
        "start_year": 1996,
        "benchmark": "$RT200",
        "benchmark_etf": "IWL",
        "top_n": 5,
        "entry_rank": 5,
        "exit_rank": 12,
        "gold_signal_index": "$RT200",
        "gold_threshold": 1.2,
        "notes": "Mega-caps. RT200/XAUUSD >= 1.2 for gold.",
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
        "gold_threshold": 36.0,
        "notes": "Only 30 stocks. DJI/XAUUSD >= 36 for gold.",
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
