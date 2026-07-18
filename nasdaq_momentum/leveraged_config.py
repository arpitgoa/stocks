"""
Leveraged ETF mapping for momentum strategy.
Maps underlying stocks to their 2x leveraged single-stock ETFs.
"""

# Stock ticker -> Leveraged ETF ticker
LEVERAGED_ETF_MAP = {
    "XAUUSD": "UGL",
    "AAPL": "AAPU",
    "AMD": "AMUU",
    "AMZN": "AMZU",
    "ARM": "ARMU",
    "AVGO": "AVGU",
    "COIN": "CONL",
    "CRWD": "CRWU",
    "GOOG": "GGLL",
    "GOOGL": "GGLL",
    "HOOD": "HODU",
    "META": "METU",
    "MSFT": "MSFU",
    "MSTR": "MSTU",
    "MU": "MUU",
    "NFLX": "NFLU",
    "NVDA": "NVDL",
    "ORCL": "ORCU",
    "PLTR": "PLTU",
    "QCOM": "QCMU",
    "SMCI": "SMCX",
    "TSLA": "TSLL",
    "TTD": "TTDU",
}

# All leveraged ETF tickers to download
LEVERAGED_ETFS = [
    "AAPU", "AMUU", "AMZU", "ARMU", "AVGU", "CONL", "CRWU", "GGLL",
    "HODU", "METU", "MSFU", "MSTU", "MUU", "NFLU", "NVDL", "ORCU",
    "PLTU", "QCMU", "SMCX", "TSLL", "TTDU",
    "TQQQ", "TNA", "SOXL", "UPRO", "GLD"
]

# Broad leveraged ETFs for benchmark comparison
BROAD_LEVERAGED = {
    "TQQQ": "3x NASDAQ-100",
    "SOXL": "3x Semiconductors",
    "TNA": "3x Russell 2000",
    "UPRO": "3x S&P 500",
}
