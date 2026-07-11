import pandas as pd

# Read all files
brkb = pd.read_csv('Berkshire Hathaway B Stock Price History.csv')
gold = pd.read_csv('Gold Futures Historical Data (1).csv')
ndx = pd.read_csv('Nasdaq 100 Historical Data (1).csv')
spy = pd.read_csv('S&P 500 Historical Data (1).csv')

# Convert Date column to datetime and set as index
for df in [brkb, gold, ndx, spy]:
    df['Date'] = pd.to_datetime(df['Date'], format='%m/%d/%Y')
    df.set_index('Date', inplace=True)
    df.sort_index(inplace=True)

# Create combined dataframe with Price column from each
combined = pd.DataFrame({
    'BRKB': brkb['Price'],
    'GOLD': gold['Price'],
    'NDX': ndx['Price'],
    'SPY': spy['Price']
})

# Remove commas and convert to float
for col in combined.columns:
    combined[col] = pd.to_numeric(combined[col].astype(str).str.replace(',', ''), errors='coerce')

# Resample to month end and forward fill
combined = combined.resample('ME').last().fillna(method='ffill')

combined.to_csv('combined_monthly_data.csv')
print(f'Combined data saved: {len(combined)} months')
print(f'\nDate range: {combined.index.min()} to {combined.index.max()}')
print(f'\nColumns: {list(combined.columns)}')
print(f'\nFirst few rows:\n{combined.head()}')
print(f'\nLast few rows:\n{combined.tail()}')
