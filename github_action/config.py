"""
Configuration for automated signal pipeline.
Defines universes, ETF sources for constituents, and strategy parameters.
"""

# ============================================================
# UNIVERSE CONFIGURATIONS
# ============================================================

UNIVERSES = {
    "nasdaq100_vix": {
        "label": "NASDAQ-100 VIX Optimized",
        "top_n": 3,
        "entry_rank": 3,
        "exit_rank": 7,
        "gold_threshold": 6.8,
        "gold_signal_index": "^NDX",
        "vix_threshold": 30,
        "vix_fast_long": 126,
        "vix_fast_short": 42,
        "constituents_source": "nasdaq100",
    },
    "nasdaq100": {
        "label": "NASDAQ-100",
        "top_n": 3,
        "entry_rank": 3,
        "exit_rank": 7,
        "gold_threshold": 7.0,
        "gold_signal_index": "^NDX",
        "vix_threshold": None,
        "constituents_source": "nasdaq100",
    },
    "sp500": {
        "label": "S&P 500",
        "top_n": 10,
        "entry_rank": 10,
        "exit_rank": 15,
        "gold_threshold": 2.2,
        "gold_signal_index": "^GSPC",
        "vix_threshold": None,
        "constituents_source": "sp500",
    },
    "sp100": {
        "label": "S&P 100",
        "top_n": 3,
        "entry_rank": 3,
        "exit_rank": 7,
        "gold_threshold": 1.0,
        "gold_signal_index": "^OEX",
        "vix_threshold": None,
        "constituents_source": "sp100",
    },
    "sp_midcap400": {
        "label": "S&P MidCap 400",
        "top_n": 5,
        "entry_rank": 5,
        "exit_rank": 10,
        "gold_threshold": 1.5,
        "gold_signal_index": "^MID",
        "vix_threshold": None,
        "constituents_source": "sp_midcap400",
    },
    "sp_smallcap600": {
        "label": "S&P SmallCap 600",
        "top_n": 10,
        "entry_rank": 10,
        "exit_rank": 20,
        "gold_threshold": 0.7,
        "gold_signal_index": "^GSPC",  # fallback
        "vix_threshold": None,
        "constituents_source": "sp_smallcap600",
    },
    "russell1000": {
        "label": "Russell 1000",
        "top_n": 3,
        "entry_rank": 3,
        "exit_rank": 7,
        "gold_threshold": 2.4,
        "gold_signal_index": "^RUI",
        "vix_threshold": None,
        "constituents_source": "russell1000",
    },
    "russell2000": {
        "label": "Russell 2000",
        "top_n": 10,
        "entry_rank": 10,
        "exit_rank": 25,
        "gold_threshold": 1.6,
        "gold_signal_index": "^RUT",
        "vix_threshold": None,
        "constituents_source": "russell2000",
    },
    "djia": {
        "label": "Dow Jones Industrial Average",
        "top_n": 3,
        "entry_rank": 3,
        "exit_rank": 7,
        "gold_threshold": 18.0,
        "gold_signal_index": "^DJI",
        "vix_threshold": None,
        "constituents_source": "djia",
    },
}

# ============================================================
# ETF HOLDINGS SOURCES (for constituent lists)
# ============================================================

# iShares/SPDR/Vanguard publish daily holdings CSVs
CONSTITUENT_SOURCES = {
    "nasdaq100": {
        "method": "wikipedia",
        "url": "https://en.wikipedia.org/wiki/Nasdaq-100#Components",
        "table_index": 5,  # may need adjustment
        "fallback_url": "https://financialmodelingprep.com/api/v3/nasdaq_constituent",
    },
    "sp500": {
        "method": "wikipedia",
        "url": "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
        "table_index": 0,
    },
    "sp100": {
        "method": "wikipedia",
        "url": "https://en.wikipedia.org/wiki/S%26P_100",
        "table_index": 2,
    },
    "djia": {
        "method": "wikipedia",
        "url": "https://en.wikipedia.org/wiki/Dow_Jones_Industrial_Average",
        "table_index": 1,
    },
    "sp_midcap400": {
        "method": "etf_holdings",
        "etf": "MDY",
        "provider": "ssga",  # State Street
    },
    "sp_smallcap600": {
        "method": "etf_holdings",
        "etf": "IJR",
        "provider": "ishares",
    },
    "russell1000": {
        "method": "etf_holdings",
        "etf": "IWB",
        "provider": "ishares",
    },
    "russell2000": {
        "method": "etf_holdings",
        "etf": "IWM",
        "provider": "ishares",
    },
}

# ============================================================
# SIGNAL TICKERS (always needed)
# ============================================================

SIGNAL_TICKERS = ["^NDX", "^GSPC", "^DJI", "^VIX", "^OEX", "^MID", "^RUI", "^RUT", "GC=F", "SPY", "QQQ", "GLD", "IWM", "DIA", "MDY", "IJR"]

# ============================================================
# LEVERAGED ETF MAP
# ============================================================

LEVERAGED_ETF_MAP = {
    "AAPL": "AAPU", "AMD": "AMUU", "AMZN": "AMZU", "ARM": "ARMU",
    "AVGO": "AVGU", "COIN": "CONL", "CRWD": "CRWU", "GOOG": "GGLL",
    "GOOGL": "GGLL", "HOOD": "HODU", "META": "METU", "MSFT": "MSFU",
    "MSTR": "MSTU", "MU": "MUU", "NFLX": "NFLU", "NVDA": "NVDL",
    "ORCL": "ORCU", "PLTR": "PLTU", "QCOM": "QCMU", "SMCI": "SMCX",
    "TSLA": "TSLL", "TTD": "TTDU",
}
