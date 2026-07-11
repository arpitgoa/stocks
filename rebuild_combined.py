import pandas as pd

# Read original files
brkb = pd.read_csv('Berkshire Hathaway B Stock Price History.csv')
gold = pd.read_csv('Gold Futures Historical Data (1).csv')
ndx = pd.read_csv('Nasdaq 100 Historical Data (1).csv')
spx = pd.read_csv('S&P 500 Historical Data (1).csv')
monthly = pd.read_csv('monthly_data.csv', index_col=0, parse_dates=True)

# Convert Date column to datetime and set as index
for df in [brkb, gold, ndx, spx]:
    df['Date'] = pd.to_datetime(df['Date'], format='%m/%d/%Y')
    df.set_index('Date', inplace=True)
    df.sort_index(inplace=True)

# Create combined dataframe
combined = pd.DataFrame({
    'BRKB': brkb['Price'],
    'GOLD': gold['Price'],
    'NDX': ndx['Price'],
    'SPX': spx['Price']
})

# Remove commas and convert to float
for col in combined.columns:
    combined[col] = pd.to_numeric(combined[col].astype(str).str.replace(',', ''), errors='coerce')

# Resample to month end
combined = combined.resample('ME').last().fillna(method='ffill')

# Add SPY and QQQ from monthly_data
spy_resampled = monthly['SPY'].resample('ME').last()
qqq_resampled = monthly['QQQ'].resample('ME').last()
combined['SPY'] = spy_resampled
combined['QQQ'] = qqq_resampled

combined.to_csv('combined_monthly_data.csv')
print(f'Combined data saved: {len(combined)} months')
print(f'\nColumns: {list(combined.columns)}')

for col in combined.columns:
    valid = combined[col].dropna()
    if len(valid) > 0:
        print(f'{col}: {valid.index[0].strftime("%Y-%m")} to {valid.index[-1].strftime("%Y-%m")} ({len(valid)} months)')

print(f'\nRows with all data: {len(combined.dropna())}')
if len(combined.dropna()) > 0:
    print(f'First complete row: {combined.dropna().index[0].strftime("%Y-%m")}')
