"""
NASDAQ-100 Historical Membership (2007–2026)
=============================================
Uses verified yearly membership data from Excel master file.
For each rebalance date, returns the correct constituents for that year.

Source: qqq_nasdaq100_master_2000_2026_single_tab.xlsx
"""

import json
import os

# Load membership data
_dir = os.path.dirname(os.path.abspath(__file__))
_membership_path = os.path.join(_dir, 'nasdaq100_membership_by_year.json')

with open(_membership_path, 'r') as f:
    MEMBERSHIP_BY_YEAR = json.load(f)


def get_members_at_date(target_date: str) -> set:
    """
    Return the set of NASDAQ-100 tickers that were members on a given date.
    target_date: 'YYYY-MM-DD'
    
    Uses yearly membership data. For dates in the first half of a year,
    uses the previous year's membership (reconstitution happens in December).
    """
    year = int(target_date[:4])
    month = int(target_date[5:7])
    
    # Reconstitution happens in December, effective ~Dec 20
    # So Jan-Dec of year X uses the membership set for year X
    # (the Excel marks 'Y' for the year the stock was a member)
    
    year_str = str(year)
    
    # If we have data for this year, use it
    if year_str in MEMBERSHIP_BY_YEAR:
        return set(MEMBERSHIP_BY_YEAR[year_str])
    
    # If before our data starts, use earliest available
    available_years = sorted(MEMBERSHIP_BY_YEAR.keys())
    if year_str < available_years[0]:
        return set(MEMBERSHIP_BY_YEAR[available_years[0]])
    
    # If after our data ends, use latest available
    if year_str > available_years[-1]:
        return set(MEMBERSHIP_BY_YEAR[available_years[-1]])
    
    # Shouldn't reach here
    return set(MEMBERSHIP_BY_YEAR[available_years[-1]])


# Print summary when run directly
if __name__ == "__main__":
    print("=" * 70)
    print("NASDAQ-100 VERIFIED MEMBERSHIP (2007-2026)")
    print("=" * 70)
    print(f"\nSource: qqq_nasdaq100_master_2000_2026_single_tab.xlsx")
    print(f"Years covered: {sorted(MEMBERSHIP_BY_YEAR.keys())}")
    
    print(f"\n{'Year':<6} {'Members':<8} {'Sample'}")
    print("-" * 60)
    for year in sorted(MEMBERSHIP_BY_YEAR.keys()):
        members = MEMBERSHIP_BY_YEAR[year]
        print(f"{year:<6} {len(members):<8} {', '.join(members[:8])} ...")
    
    # Show all tickers ever in the index
    all_tickers = set()
    for members in MEMBERSHIP_BY_YEAR.values():
        all_tickers.update(members)
    print(f"\nTotal unique tickers across all years: {len(all_tickers)}")
