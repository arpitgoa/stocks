"""
Download daily price data for all NASDAQ-100 historical constituents (2005-2026).
Single batch fetch using yfinance.
All 258 tickers that have ever been in NASDAQ-100 from 2007-2026.
"""

import yfinance as yf
import pandas as pd
from datetime import datetime

# All 258 tickers ever in NASDAQ-100 (2007-2026)
# Source: qqq_nasdaq100_master_2000_2026_single_tab.xlsx
ALL_TICKERS = [
    "AAL", "AAPL", "ABNB", "ADBE", "ADI", "ADP", "ADSK", "AEP", "AEOS",
    "AKAM", "ALGN", "ALNY", "ALTR", "ALXN", "AMAT", "AMD", "AMGN", "AMLN",
    "AMZN", "ANSS", "APCC", "APOL", "APP", "ARM", "ASML", "ATVI", "AVGO",
    "AXON", "AZN", "BBBY", "BEAS", "BIDU", "BIIB", "BKR", "BKNG", "BMC",
    "BMET", "BMRN", "BRCM", "CA", "CCEP", "CDW", "CDNS", "CDWC", "CEG",
    "CELG", "CEPH", "CERN", "CHKP", "CHRW", "CHTR", "CIEN", "CKFR", "CMCSA",
    "CMVT", "COIN", "COST", "CPRT", "CRWD", "CSCO", "CSGP", "CSX", "CTAS",
    "CTSH", "CTRP", "CTRX", "CTXS", "DASH", "DDOG", "DELL", "DISH", "DISCA",
    "DISCK", "DLTR", "DOCU", "DTV", "DXCM", "EA", "EBAY", "ENDP", "ENPH",
    "EQIX", "ERIC", "ERTS", "ESRX", "EXC", "EXPE", "EXPD", "FANG", "FAST",
    "FB", "FER", "FFIV", "FISV", "FLEX", "FLIR", "FMCN", "FOSL", "FOX",
    "FOXA", "FSLR", "FTNT", "FWLT", "GEHC", "GENZ", "GFS", "GILD", "GMCR",
    "GOLD", "GOOG", "GOOGL", "GRMN", "HANS", "HAS", "HON", "HOLX", "HOOD",
    "HSIC", "IACI", "IDXX", "ILMN", "INCY", "INFN", "INFY", "INSM", "INTC",
    "INTU", "ISRG", "JAVA", "JBHT", "JD", "JNPR", "JOYG", "KDP", "KHC",
    "KLAC", "KRFT", "LAMR", "LBTYA", "LBTYK", "LCID", "LEAP", "LIFE", "LIN",
    "LITE", "LLTC", "LMCA", "LMCK", "LOGI", "LRCX", "LULU", "LUMN", "LVLT",
    "LVNTA", "MAR", "MAT", "MCHP", "MDB", "MDLZ", "MEDI", "MELI", "META",
    "MICC", "MNST", "MPWR", "MRNA", "MRVL", "MSFT", "MSTR", "MTCH", "MU",
    "MXIM", "MYL", "NCLH", "NFLX", "NIHD", "NLOK", "NTAP", "NTES", "NTLI",
    "NUAN", "NVDA", "NWSA", "NXPI", "ODFL", "OKTA", "ON", "ORCL", "ORLY",
    "PANW", "PAYX", "PCAR", "PCLN", "PDD", "PDCO", "PEP", "PETM", "PLTR",
    "PPDI", "PRGO", "PTEN", "PTON", "PYPL", "QCOM", "QGEN", "QRTEA", "REGN",
    "RIMM", "RIVN", "ROP", "ROST", "RYAAY", "SBAC", "SBUX", "SEBL", "SEPR",
    "SGEN", "SHLD", "SHPG", "SHOP", "SIAL", "SIRI", "SMCI", "SNDK", "SNPS",
    "SOLS", "SPLK", "SPLS", "SRCL", "STX", "STLD", "SWKS", "SYMC", "TCOM",
    "TEAM", "TEVA", "TLAB", "TMUS", "TRI", "TRGP", "TRIP", "TSCO", "TSLA",
    "TTD", "TTWO", "TXN", "UAUA", "UAL", "ULTA", "URBN", "VIAB", "VIP",
    "VMED", "VOD", "VRSK", "VRSN", "VRTX", "VSNT", "WBA", "WBD", "WCRX",
    "WDC", "WDAY", "WFM", "WFMI", "WLTW", "WMT", "WYNN", "XEL", "XLNX",
    "XMSR", "XRAY", "YHOO", "ZM", "ZS",
]

print(f"Total tickers: {len(ALL_TICKERS)}")
print("Downloading 20 years of daily data...")

# Single batch download — no loop needed
data = yf.download(
    ALL_TICKERS,
    start="2005-01-01",
    end=datetime.now().strftime("%Y-%m-%d"),
    auto_adjust=True,
    progress=True,
)

# Save close prices as CSV
close_prices = data["Close"]
print(f"\nShape: {close_prices.shape}")
print(f"Date range: {close_prices.index[0]} to {close_prices.index[-1]}")
print(f"Tickers with data: {close_prices.dropna(axis=1, how='all').shape[1]}")

close_prices.to_csv("nasdaq100_daily_closes.csv")
print("\nSaved to: nasdaq100_daily_closes.csv")
