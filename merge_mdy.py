import pandas as pd

# Read combined data first
combined = pd.read_csv('/Users/ajhanwa/workspace/stocks/combined_monthly_data.csv')

# Remove columns if they exist
for col in ['IWM', 'IWM_x', 'IWM_y']:
    if col in combined.columns:
        combined = combined.drop(col, axis=1)

# Read IWM file
iwm = pd.read_csv('/Users/ajhanwa/workspace/stocks/IWM ETF Stock Price History (1).csv')

# Parse date and create year-month column in YYYY-MM format
iwm['Date'] = pd.to_datetime(iwm['Date'], format='%m/%d/%Y')
iwm['YearMonth'] = iwm['Date'].dt.strftime('%Y-%m')

# Keep only the Price column and rename it
iwm_monthly = iwm[['YearMonth', 'Price']].copy()
iwm_monthly.columns = ['YearMonth', 'IWM']

# Extract year-month from combined data
combined['YearMonth'] = pd.to_datetime(combined['Date']).dt.strftime('%Y-%m')

# Merge on YearMonth
merged = pd.merge(combined, iwm_monthly, on='YearMonth', how='left')

# Drop the temporary YearMonth column
merged = merged.drop('YearMonth', axis=1)

# Save back
merged.to_csv('/Users/ajhanwa/workspace/stocks/combined_monthly_data.csv', index=False)

print(f"✓ Merged IWM data into combined_monthly_data.csv")
print(f"  Total rows: {len(merged)}")
print(f"  IWM values added: {merged['IWM'].notna().sum()}")
