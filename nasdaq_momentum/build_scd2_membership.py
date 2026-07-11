"""
Build NASDAQ-100 SCD Type 2 membership table from Wikipedia change history.
Every add/remove event from Feb 2007 to July 2026.

Output: nasdaq100_scd2.csv with columns: ticker, start_date, end_date
Where end_date = None means still active.
"""

import pandas as pd
from datetime import datetime

# All changes from Wikipedia, chronological order
# Format: (date, added_ticker, removed_ticker)
# Some rows have only add or only remove (mid-year special events)
CHANGES = [
    # === 2007 ===
    ("2007-02-01", "LOGI", "CMVT"),
    ("2007-02-14", "RYAAY", "APCC"),
    ("2007-03-08", "UAUA", "AEOS"),
    ("2007-06-01", "CEPH", "MEDI"),
    ("2007-07-12", "FWLT", "BMET"),
    ("2007-08-27", "VMED", "NTLI"),
    ("2007-10-08", "LEAP", "CDWC"),
    ("2007-12-04", "BIDU", "CKFR"),
    ("2007-12-24", "HOLX", "ERIC"),
    ("2007-12-24", "FMCN", "PTEN"),
    ("2007-12-24", "HANS", "ROST"),
    ("2007-12-24", "STLD", "SEPR"),
    ("2007-12-24", "SRCL", "XMSR"),
    # === 2008 ===
    ("2008-04-30", "DTV", "BEAS"),
    ("2008-05-19", "CA", "TLAB"),
    ("2008-07-21", "FLIR", "UAUA"),
    ("2008-11-10", "STX", "MNST"),   # Monster Worldwide, not Monster Beverage
    ("2008-12-22", "ADP", "AMLN"),
    ("2008-12-22", "FSLR", "CDNS"),
    ("2008-12-22", "LIFE", "DISCA"),
    ("2008-12-22", "ROST", "LAMR"),
    ("2008-12-22", "MXIM", "LEAP"),
    ("2008-12-22", "ILMN", "LVLT"),
    ("2008-12-22", "PPDI", "PETM"),
    ("2008-12-22", "ORLY", "SIRI"),
    ("2008-12-22", "URBN", "SNDK"),
    ("2008-12-22", "JBHT", "VMED"),
    ("2008-12-22", "WCRX", "WFMI"),
    ("2009-01-20", "NWSA", "FMCN"),
    # === 2009 ===
    ("2009-07-17", "CERN", "JAVA"),
    ("2009-10-29", "PCLN", "JNPR"),
    ("2009-12-21", "VOD", "AKAM"),
    ("2009-12-21", "MAT", "HANS"),
    ("2009-12-21", "BMC", "IACI"),
    ("2009-12-21", "MYL", "LBTYA"),
    ("2009-12-21", "QGEN", "PPDI"),
    ("2009-12-21", "SNDK", "RYAAY"),
    ("2009-12-21", "VMED", "STLD"),
    # === 2010 ===
    ("2010-12-20", "AKAM", "CTAS"),
    ("2010-12-20", "TCOM", "DISH"),
    ("2010-12-20", "DLTR", "FWLT"),
    ("2010-12-20", "FFIV", "HOLX"),
    ("2010-12-20", "MU", "JBHT"),
    ("2010-12-20", "NFLX", "LOGI"),
    ("2010-12-20", "WFM", "PDCO"),
    # === 2011 ===
    ("2011-04-04", "ALXN", "GENZ"),
    ("2011-05-27", "GMCR", "MICC"),
    ("2011-07-15", "SIRI", "CEPH"),
    ("2011-12-06", "PRGO", "JOYG"),
    ("2011-12-19", "AVGO", "FLIR"),
    ("2011-12-19", "FOSL", "ILMN"),
    ("2011-12-19", "MNST", "NIHD"),
    ("2011-12-19", "NUAN", "QGEN"),
    ("2011-12-19", "GOLD", "URBN"),
    # === 2012 ===
    ("2012-04-23", "TXN", "FSLR"),
    ("2012-05-30", "VIAB", "TEVA"),
    ("2012-07-23", "KFT", "TCOM"),
    ("2012-12-12", "META", "INFY"),
    ("2012-12-24", "ADI", "APOL"),
    ("2012-12-24", "CTRX", "EA"),
    ("2012-12-24", "DISCA", "FLEX"),
    ("2012-12-24", "EQIX", "GMCR"),
    ("2012-12-24", "LBTYA", "LRCX"),
    ("2012-12-24", "LMCA", "MRVL"),
    ("2012-12-24", "REGN", "NFLX"),
    ("2012-12-24", "SBAC", "RIMM"),
    ("2012-12-24", "VRSK", "VRSN"),
    ("2012-12-24", "WDC", "WCRX"),
    # === 2013 ===
    ("2013-01-15", "STRZA", "LMCA"),
    ("2013-03-18", "KRFT", "STRZA"),
    ("2013-06-05", "LMCA", "VMED"),
    ("2013-06-06", "NFLX", "PRGO"),
    ("2013-07-15", "TSLA", "ORCL"),
    ("2013-07-25", "CHTR", "BMC"),
    ("2013-08-22", "GMCR", "LIFE"),
    ("2013-10-29", "VIP", "DELL"),
    ("2013-11-18", "MAR", "GOLD"),
    ("2013-12-23", "DISH", "FOSL"),
    ("2013-12-23", "ILMN", "MCHP"),
    ("2013-12-23", "NXPI", "NUAN"),
    ("2013-12-23", "TRIP", "SHLD"),
    ("2013-12-23", "TSCO", "XRAY"),
    # === 2014 ===
    ("2014-04-03", "GOOGL", None),
    ("2014-12-22", "AAL", "EXPE"),
    ("2014-12-22", "EA", "FFIV"),
    ("2014-12-22", "LRCX", "MXIM"),
    ("2014-12-22", "CMCSA", None),
    ("2014-12-22", "FOX", None),
    ("2014-12-22", "LBTYK", None),
    # === 2015 ===
    ("2015-03-23", "WBA", "EQIX"),
    ("2015-07-02", "KHC", "KRFT"),
    ("2015-07-02", "LILA", None),
    ("2015-07-02", "LILAK", None),
    ("2015-07-24", None, "DTV"),
    ("2015-07-24", None, "CTRX"),
    ("2015-07-27", "BMRN", None),
    ("2015-07-29", "JD", None),
    ("2015-07-31", None, "SIAL"),
    ("2015-08-03", "SWKS", None),
    ("2015-10-07", "INCY", "ALTR"),
    ("2015-11-11", "PYPL", "BRCM"),
    ("2015-12-21", "TCOM", "CHRW"),
    ("2015-12-21", "ENDP", "EXPD"),
    ("2015-12-21", "EXPE", "GMCR"),
    ("2015-12-21", "MXIM", "GRMN"),
    ("2015-12-21", "NCLH", "SPLS"),
    ("2015-12-21", "TMUS", "VIP"),
    ("2015-12-21", "ULTA", "WYNN"),
    ("2015-12-21", None, "LILA"),
    ("2015-12-21", None, "LILAK"),
    # === 2016 ===
    ("2016-02-01", "AVGO", None),      # Name change from BRCM
    ("2016-02-16", "CSX", "KLAC"),
    ("2016-03-16", "NTES", "SNDK"),
    ("2016-06-20", "XRAY", "LMCA"),
    ("2016-06-20", None, "LMCK"),
    ("2016-06-20", None, "BATRA"),
    ("2016-06-20", None, "BATRK"),
    ("2016-04-18", "BATRA", None),
    ("2016-04-18", "BATRK", None),
    ("2016-07-18", "MCHP", "ENDP"),
    ("2016-10-19", "SHPG", "LLTC"),
    ("2016-12-19", "CTAS", "BBBY"),
    ("2016-12-19", "HAS", "NTAP"),
    ("2016-12-19", "HOLX", "SRCL"),
    ("2016-12-19", "KLAC", "WFM"),
    # === 2017 ===
    ("2017-02-07", "JBHT", "NXPI"),
    ("2017-03-20", "IDXX", "SBAC"),
    ("2017-04-24", "WYNN", "TRIP"),
    ("2017-06-19", "MELI", "YHOO"),
    ("2017-10-23", "ALGN", "MAT"),
    ("2017-12-18", "ASML", "AKAM"),
    ("2017-12-18", "CDNS", "DISCA"),
    ("2017-12-18", None, "DISCK"),
    ("2017-12-18", "SNPS", "NCLH"),
    ("2017-12-18", "TTWO", "TSCO"),
    ("2017-12-18", "WDAY", "VIAB"),
    # === 2018 ===
    ("2018-07-23", "PEP", "DISH"),
    ("2018-11-05", "NXPI", "CA"),
    ("2018-11-19", "XEL", "XRAY"),
    ("2018-12-24", "AMD", "ESRX"),
    ("2018-12-24", "LULU", "HOLX"),
    ("2018-12-24", "NTAP", "QRTEA"),
    ("2018-12-24", "UAL", "SHPG"),
    ("2018-12-24", "VRSN", "STX"),
    ("2018-12-24", "WTW", "VOD"),
    # === 2019 ===
    ("2019-03-19", "FOXA", "FOXA"),    # Fox Corp replaced 21CF - same ticker
    ("2019-03-19", "FOX", "FOX"),      # Fox Corp replaced 21CF - same ticker
    ("2019-11-21", "EXC", "CELG"),
    ("2019-12-23", "ANSS", "HAS"),
    ("2019-12-23", "CDW", "HSIC"),
    ("2019-12-23", "CPRT", "JBHT"),
    ("2019-12-23", "CSGP", "MYL"),
    ("2019-12-23", "SGEN", "NLOK"),
    ("2019-12-23", "SPLK", "WYNN"),
    # === 2020 ===
    ("2020-04-20", "DXCM", "AAL"),
    ("2020-04-30", "ZM", "WTW"),
    ("2020-06-22", "DOCU", "UAL"),
    ("2020-07-20", "MRNA", "CSGP"),
    ("2020-08-24", "PDD", "NTAP"),
    ("2020-10-19", "KDP", "WDC"),
    ("2020-12-21", "AEP", "BMRN"),
    ("2020-12-21", "MRVL", "CTXS"),
    ("2020-12-21", "MTCH", "EXPE"),
    ("2020-12-21", "OKTA", "LBTYA"),
    ("2020-12-21", None, "LBTYK"),
    ("2020-12-21", "PTON", "TTWO"),
    ("2020-12-21", "TEAM", "ULTA"),
    # === 2021 ===
    ("2021-07-21", "HON", "ALXN"),
    ("2021-08-26", "CRWD", "MXIM"),
    ("2021-12-20", "ABNB", "CDW"),
    ("2021-12-20", "FTNT", "FOXA"),
    ("2021-12-20", None, "FOX"),
    ("2021-12-20", "PANW", "CERN"),
    ("2021-12-20", "LCID", "CHKP"),
    ("2021-12-20", "ZS", "TCOM"),
    ("2021-12-20", "DDOG", "INCY"),
    # === 2022 ===
    ("2022-01-24", "ODFL", "PTON"),
    ("2022-02-02", "CEG", None),       # Spinoff from EXC
    ("2022-02-22", "AZN", "XLNX"),
    ("2022-11-21", "ENPH", "OKTA"),
    ("2022-12-19", "CSGP", "VRSN"),
    ("2022-12-19", "RIVN", "SWKS"),
    ("2022-12-19", "NTES", None),      # Removed per recon
    ("2022-12-19", "WBD", "SPLK"),
    ("2022-12-19", "GFS", "BIDU"),
    ("2022-12-19", "BKR", "MTCH"),
    ("2022-12-19", "FANG", "DOCU"),
    # === 2023 ===
    ("2023-06-07", "GEHC", "FISV"),
    ("2023-06-20", "ON", "RIVN"),
    ("2023-07-17", "TTD", "ATVI"),
    ("2023-12-14", "TTWO", "SGEN"),
    ("2023-12-18", "CDW", "ALGN"),
    ("2023-12-18", "CCEP", "EBAY"),
    ("2023-12-18", "DASH", "ENPH"),
    ("2023-12-18", "MDB", "JD"),
    ("2023-12-18", "ROP", "LCID"),
    ("2023-12-18", "SPLK", "ZM"),
    # === 2024 ===
    ("2024-03-18", "LIN", "SPLK"),
    ("2024-06-24", "ARM", "SIRI"),
    ("2024-07-22", "SMCI", "WBA"),
    ("2024-11-18", "APP", "DLTR"),
    ("2024-12-23", "PLTR", "ILMN"),
    ("2024-12-23", "MSTR", "MRNA"),
    ("2024-12-23", "AXON", "SMCI"),
    # === 2025 ===
    ("2025-05-19", "SHOP", "MDB"),
    ("2025-07-17", None, "ANSS"),      # Ansys acquired by Synopsys
    ("2025-07-28", "TRI", None),       # Thomson Reuters transferred listing
    ("2025-12-22", "ALNY", "BIIB"),
    ("2025-12-22", "FER", "CDW"),
    ("2025-12-22", "INSM", "GFS"),
    ("2025-12-22", "MPWR", "LULU"),
    ("2025-12-22", "STX", "ON"),
    ("2025-12-22", "WDC", "TTD"),
    # === 2026 ===
    ("2026-01-20", "WMT", "AZN"),
    ("2026-01-20", "WBD", None),       # Versant/WBD spin
    ("2026-04-20", "SNDK", "TEAM"),
    ("2026-05-18", "LITE", "CSGP"),
    ("2026-06-22", "ALAB", "CHTR"),
    ("2026-06-22", "CRWV", "CTSH"),
    ("2026-06-22", "NBIS", "INSM"),
    ("2026-06-22", "RKLB", "VRSK"),
    ("2026-06-22", "TER", "ZS"),
]

# Starting roster BEFORE the first change (Feb 1, 2007)
# = Current members, undo ALL changes backward
def compute_starting_roster():
    members = set([
        "NVDA","AAPL","MU","MSFT","AMZN","AMD","GOOGL","TSLA","GOOG","INTC",
        "AVGO","META","WMT","AMAT","LRCX","CSCO","COST","KLAC","NFLX","SNDK",
        "TXN","PLTR","PANW","LIN","MRVL","WDC","STX","QCOM","TMUS","PEP",
        "AMGN","ADI","CRWD","ASML","GILD","HON","APP","ISRG","SHOP","ARM",
        "BKNG","VRTX","SBUX","FTNT","CDNS","MAR","CEG","MNST","ADP","CSX",
        "SNPS","MELI","CMCSA","ADBE","DDOG","MDLZ","AEP","DASH","ORLY","INTU",
        "NXPI","ROST","CTAS","TER","ALAB","WBD","REGN","MPWR","LITE","PCAR",
        "ABNB","BKR","FAST","NBIS","XEL","EA","PDD","FANG","FER","RKLB",
        "EXC","MCHP","KDP","ODFL","CCEP","TTWO","IDXX","CRWV","ADSK","PYPL",
        "ALNY","AXON","PAYX","ROP","TRI","GEHC","CPRT","KHC","MSTR","DXCM",
        "WDAY",
    ])
    
    # Walk backward through all changes
    for date, added, removed in reversed(CHANGES):
        if added and added in members:
            members.discard(added)
        if removed:
            members.add(removed)
    
    return members


print("Computing starting roster (pre-Feb 2007)...")
starting = compute_starting_roster()
print(f"Starting roster: {len(starting)} members")
print(f"Members: {sorted(starting)}")

# Now walk FORWARD to build SCD2
print("\nBuilding SCD Type 2 table...")

members = set(starting)
scd2_records = []

# Track when each ticker entered
entry_dates = {t: "2007-01-01" for t in members}  # All starting members enter Jan 1 2007

for date, added, removed in CHANGES:
    if removed and removed in members:
        members.discard(removed)
        scd2_records.append({
            "ticker": removed,
            "start_date": entry_dates.get(removed, "2007-01-01"),
            "end_date": date,
        })
        if removed in entry_dates:
            del entry_dates[removed]
    
    if added:
        members.add(added)
        entry_dates[added] = date

# Close out still-active members
for ticker in members:
    scd2_records.append({
        "ticker": ticker,
        "start_date": entry_dates.get(ticker, "2007-01-01"),
        "end_date": None,  # Still active
    })

# Save
df = pd.DataFrame(scd2_records)
df = df.sort_values(["ticker", "start_date"]).reset_index(drop=True)
df.to_csv("nasdaq100_scd2.csv", index=False)

print(f"\nSCD2 table: {len(df)} records")
print(f"Unique tickers: {df['ticker'].nunique()}")
print(f"Currently active: {df['end_date'].isna().sum()}")
print(f"\nSaved to: nasdaq100_scd2.csv")

# Verify counts at key dates
print("\n\nMembership counts at key dates:")
print("-" * 40)
for check_date in ["2007-06-01","2008-06-01","2009-06-01","2010-06-01",
                   "2012-06-01","2014-06-01","2016-06-01","2018-06-01",
                   "2020-06-01","2022-06-01","2024-06-01","2026-07-01"]:
    count = len(df[(df['start_date'] <= check_date) & 
                   ((df['end_date'].isna()) | (df['end_date'] > check_date))])
    print(f"  {check_date}: {count} members")

# Also rebuild the JSON membership by year
print("\n\nBuilding yearly membership JSON...")
membership = {}
for year in range(2007, 2027):
    check_date = f"{year}-06-01"
    active = df[(df['start_date'] <= check_date) & 
                ((df['end_date'].isna()) | (df['end_date'] > check_date))]
    membership[str(year)] = sorted(active['ticker'].tolist())

import json
with open("nasdaq100_membership_by_year.json", "w") as f:
    json.dump(membership, f, indent=2)
print("Saved nasdaq100_membership_by_year.json")
