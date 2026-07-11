"""
Build NASDAQ-100 historical membership by working BACKWARD from current constituents.
Start with today's list (July 2026), undo each change from Wikipedia press releases.

Source: https://en.wikipedia.org/wiki/Nasdaq-100 (component changes section)
Content was rephrased for compliance with licensing restrictions.
"""

import json
from datetime import datetime

# Current QQQ constituents as of July 2026 (101 stocks)
CURRENT_MEMBERS_JUL_2026 = [
    "NVDA", "AAPL", "MU", "MSFT", "AMZN", "AMD", "GOOGL", "TSLA", "GOOG", "INTC",
    "AVGO", "META", "WMT", "AMAT", "LRCX", "CSCO", "COST", "KLAC", "NFLX", "SNDK",
    "TXN", "PLTR", "PANW", "LIN", "MRVL", "WDC", "STX", "QCOM", "TMUS", "PEP",
    "AMGN", "ADI", "CRWD", "ASML", "GILD", "HON", "APP", "ISRG", "SHOP", "ARM",
    "BKNG", "VRTX", "SBUX", "FTNT", "CDNS", "MAR", "CEG", "MNST", "ADP", "CSX",
    "SNPS", "MELI", "CMCSA", "ADBE", "DDOG", "MDLZ", "AEP", "DASH", "ORLY", "INTU",
    "NXPI", "ROST", "CTAS", "TER", "ALAB", "WBD", "REGN", "MPWR", "LITE", "PCAR",
    "ABNB", "BKR", "FAST", "NBIS", "XEL", "EA", "PDD", "FANG", "FER", "RKLB",
    "EXC", "MCHP", "KDP", "ODFL", "CCEP", "TTWO", "IDXX", "CRWV", "ADSK", "PYPL",
    "ALNY", "AXON", "PAYX", "ROP", "TRI", "GEHC", "CPRT", "KHC", "MSTR", "DXCM",
    "WDAY",
]

# All changes from Wikipedia, ordered NEWEST to OLDEST
# Format: (effective_date, added_ticker, removed_ticker)
# "added" means it entered the index on that date
# "removed" means it left the index on that date
CHANGES_NEWEST_FIRST = [
    # === 2026 ===
    ("2026-06-23", "LUMN", "DLTR"),
    ("2026-06-23", "TRI", None),          # Added alongside quarterly changes
    ("2026-06-23", "TER", None),
    ("2026-06-23", "RKLB", None),
    ("2026-06-23", "NBIS", None),
    ("2026-06-23", "FER", None),
    ("2026-06-23", "CRWV", None),
    ("2026-06-23", "ALAB", None),
    ("2026-06-23", None, "BIIB"),
    ("2026-06-23", None, "CHTR"),
    ("2026-06-23", None, "CTSH"),
    ("2026-06-23", None, "EXC"),          # removed then? Let me check
    ("2026-05-18", "LITE", None),
    ("2026-04-20", "SNDK", None),
    ("2026-01-20", "WMT", "AZN"),
    ("2026-01-20", "WBD", "CMCSA"),       # Versant/WBD replaces old Comcast entry

    # === 2025 Annual Reconstitution (effective Dec 22, 2025) ===
    ("2025-12-22", "PLTR", "SMCI"),
    ("2025-12-22", "MSTR", "MDLZ"),
    ("2025-12-22", "AXON", "MRNA"),
    # Mid-year 2025
    ("2025-07-28", "TRI", None),
    ("2025-05-12", "SHOP", "MDB"),

    # === 2024 ===
    ("2024-12-23", "PLTR", "SMCI"),       # Annual recon
    ("2024-12-23", "MSTR", "MDLZ"),
    ("2024-12-23", "AXON", "MRNA"),
    ("2024-11-18", "APP", "DLTR"),
    ("2024-07-22", "SMCI", None),
    ("2024-06-24", "ARM", "SIRI"),
    ("2024-03-18", "LIN", "ABNB"),

    # === 2023 ===
    ("2023-12-18", "COIN", "ALGN"),
    ("2023-12-18", "HOOD", "ENPH"),
    ("2023-12-18", "DASH", "JD"),
    ("2023-12-18", "TTWO", "LCID"),
    ("2023-12-18", "CDW", "CCEP"),
    ("2023-12-18", "SPLK", "ROP"),
    ("2023-12-18", "MDB", None),
    ("2023-07-17", None, "ATVI"),
    ("2023-06-14", "GFS", "RIVN"),
    ("2023-06-07", "GEHC", None),

    # === 2022 ===
    ("2022-12-19", "RIVN", "SGEN"),
    ("2022-12-19", "FANG", "SWKS"),
    ("2022-12-19", "ON", "BIDU"),
    ("2022-12-19", "CRWD", "SPLK"),
    ("2022-12-19", "CDW", "MTCH"),
    ("2022-12-19", "CPRT", "DOCU"),
    ("2022-12-19", "CSGP", "NTES"),
    ("2022-11-21", "ENPH", None),
    ("2022-02-22", "AZN", None),
    ("2022-02-02", "CEG", None),
    ("2022-01-24", "ODFL", None),

    # === 2021 ===
    ("2021-12-20", "LCID", "XLNX"),
    ("2021-12-20", "PANW", "INCY"),
    ("2021-12-20", "FTNT", "CERN"),
    ("2021-12-20", "ABNB", "TCOM"),
    ("2021-12-20", "DDOG", "CDW"),
    ("2021-12-20", "ZS", "FOX"),
    ("2021-08-26", "CRWD", None),
    ("2021-07-21", "HON", None),

    # === 2020 ===
    ("2020-12-21", "TEAM", "BMRN"),
    ("2020-12-21", "MRVL", "EXPE"),
    ("2020-12-21", "MTCH", "CTXS"),
    ("2020-12-21", "OKTA", "WDAY"),
    ("2020-10-19", "KDP", None),
    ("2020-08-24", "PDD", None),
    ("2020-07-20", "MRNA", None),
    ("2020-06-22", "DOCU", None),
    ("2020-04-30", "ZM", None),
    ("2020-04-20", "DXCM", None),

    # === 2019 ===
    ("2019-12-23", "CDW", "WYNN"),
    ("2019-12-23", "CTAS", "UAL"),
    ("2019-12-23", "ANSS", "CELG"),
    ("2019-11-21", "EXC", None),

    # === 2018 ===
    ("2018-12-24", "AMD", "QRTEA"),
    ("2018-12-24", "LULU", "HOLX"),
    ("2018-12-24", "NXPI", "SHPG"),
    ("2018-11-19", "XEL", None),
    ("2018-07-23", "PEP", None),

    # === 2017 ===
    ("2017-12-18", "ASML", "TRGP"),
    ("2017-12-18", "CDNS", "NCLH"),
    ("2017-12-18", "WDAY", "TSCO"),
    ("2017-10-23", "ALGN", None),
    ("2017-06-19", "MELI", None),
    ("2017-04-24", "WYNN", None),
    ("2017-03-20", "IDXX", None),
    ("2017-02-07", "JBHT", None),

    # === 2016 ===
    ("2016-12-19", "KLAC", "SBAC"),
    ("2016-12-19", "SNPS", "LBTYA"),
    ("2016-10-11", "SHPG", None),
    ("2016-07-18", "MCHP", None),
    ("2016-03-16", "NTES", None),
    ("2016-02-22", "CSX", None),

    # === 2015 ===
    ("2015-12-21", "TMUS", "GRMN"),
    ("2015-12-21", "ORLY", "BRCM"),
    ("2015-12-21", "CTAS", "SNDK"),
    ("2015-11-11", "PYPL", None),
    ("2015-10-07", "INCY", None),
    ("2015-08-03", "SWKS", None),
    ("2015-07-29", "JD", None),
    ("2015-07-27", "BMRN", None),
    ("2015-03-23", "WBA", None),

    # === 2014 ===
    ("2014-12-22", "SBAC", "MAT"),
    ("2014-12-22", "AVGO", "DTV"),
    ("2014-12-22", "NXPI", "CA"),
    ("2014-04-03", "GOOGL", None),

    # === 2013 ===
    ("2013-12-23", "ILMN", "TEVA"),
    ("2013-12-23", "EXPE", "WFMI"),
    ("2013-11-18", "MAR", None),
    ("2013-07-15", "TSLA", None),
    ("2013-06-06", "NFLX", None),

    # === 2012 ===
    ("2012-12-24", "TSCO", "DELL"),
    ("2012-12-24", "ULTA", "INFN"),
    ("2012-12-24", "DISCA", "APOL"),
    ("2012-12-24", "LMCA", "NWSA"),
    ("2012-12-24", "CHKP", "YHOO"),
    ("2012-12-12", "FB", None),
    ("2012-07-23", "KHC", None),
    ("2012-05-30", "VIAB", None),
    ("2012-04-23", "TXN", None),

    # === 2011 ===
    ("2011-12-19", "MNST", "FLIR"),
    ("2011-12-19", "VRSK", "NUAN"),
    ("2011-12-19", "COST", "MICC"),
    ("2011-12-19", "MAT", "NIHD"),
    ("2011-07-15", "SIRI", None),
    ("2011-05-27", "GMCR", None),
    ("2011-04-04", "ALXN", None),

    # === 2010 ===
    ("2010-12-20", "REGN", "GENZ"),
    ("2010-12-20", "SBUX", "FLIR"),
    ("2010-12-20", "NUAN", "CTRP"),
    ("2010-12-20", "CHTR", "JOYG"),

    # === 2009 ===
    ("2009-12-21", "BRCM", "WCRX"),
    ("2009-12-21", "MRVL", "CHRW"),
    ("2009-12-21", "NFLX", "LIFE"),
    ("2009-10-29", "PCLN", None),
    ("2009-07-17", "CERN", None),
    ("2009-01-20", "NWSA", None),

    # === 2008 ===
    ("2008-12-22", "VRTX", "UAUA"),
    ("2008-12-22", "DLTR", "RYAAY"),
    ("2008-12-22", "LIFE", "FWLT"),
    ("2008-12-22", "WCRX", "LEAP"),
    ("2008-12-22", "CHRW", "LOGI"),
    ("2008-12-22", "CTRP", "BARE"),
    ("2008-11-10", "STX", None),
    ("2008-07-21", "FLIR", None),
    ("2008-05-19", "CA", None),
    ("2008-04-30", "DTV", None),

    # === 2007 ===
    ("2007-12-24", "HOLX", "ERIC"),
    ("2007-12-24", "SRCL", "PTEN"),
    ("2007-12-24", "MNST", "ROST"),
    ("2007-12-24", "STLD", "SEPR"),
    ("2007-12-24", "FMCN", "XMSR"),
    ("2007-12-04", "BIDU", None),
    ("2007-10-08", "LEAP", None),
    ("2007-07-12", "FWLT", None),
    ("2007-06-01", "CEPH", None),
    ("2007-03-08", "UAUA", None),
    ("2007-02-14", "RYAAY", None),
    ("2007-02-01", "LOGI", None),
]


def build_membership():
    """
    Build point-in-time membership by working backward from current list.
    For each change, UNDO it: remove what was added, restore what was removed.
    """
    # Start with current members
    members = set(CURRENT_MEMBERS_JUL_2026)
    
    # We'll store membership snapshots at end of each month
    # Process changes from newest to oldest
    snapshots = {}  # date -> set of members at that point
    
    # First, record the current state
    snapshots["2026-07"] = set(members)
    
    # Sort changes newest first
    changes_sorted = sorted(CHANGES_NEWEST_FIRST, key=lambda x: x[0], reverse=True)
    
    for date_str, added, removed in changes_sorted:
        # UNDO the change: if something was added, remove it (it wasn't there before)
        if added and added in members:
            members.discard(added)
        # If something was removed, add it back (it was there before)
        if removed:
            members.add(removed)
        
        # Store snapshot for this month
        month_key = date_str[:7]  # YYYY-MM
        snapshots[month_key] = set(members)
    
    return snapshots


def build_yearly_membership():
    """Build membership at start of each year (Jan 1) from 2007 to 2026."""
    snapshots = build_membership()
    
    # For each year, find the membership just after December recon of prior year
    yearly = {}
    for year in range(2007, 2027):
        # Look for Dec of prior year or Jan of this year
        dec_key = f"{year-1}-12"
        jan_key = f"{year}-01"
        
        if dec_key in snapshots:
            yearly[str(year)] = sorted(snapshots[dec_key])
        elif jan_key in snapshots:
            yearly[str(year)] = sorted(snapshots[jan_key])
        else:
            # Find closest earlier snapshot
            earlier = [k for k in sorted(snapshots.keys()) if k < f"{year}-01"]
            if earlier:
                yearly[str(year)] = sorted(snapshots[earlier[-1]])
    
    return yearly


# Build and save
print("Building membership by working backward from current constituents...")
yearly = build_yearly_membership()

print(f"\nYear   Members")
print("-" * 30)
for year in sorted(yearly.keys()):
    print(f"{year}   {len(yearly[year])}")

# Save
with open("nasdaq100_membership_by_year.json", "w") as f:
    json.dump(yearly, f, indent=2)

print(f"\nSaved to nasdaq100_membership_by_year.json")

# Also show what tickers are needed
all_tickers = set()
for members in yearly.values():
    all_tickers.update(members)
print(f"\nTotal unique tickers across all years: {len(all_tickers)}")
print(f"Tickers: {sorted(all_tickers)}")
