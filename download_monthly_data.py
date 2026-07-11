import pandas as pd

# Original tickers
original = ['BRK-B', 'QQQ', 'SPY', '^GSPC', 'GLD', 'GOLD', 'NDX', 'GC=F', 'XAUUSD=X']

# Read IWM holdings
df = pd.read_csv('/Users/ajhanwa/Downloads/IWM_holdings.csv', skiprows=14)
iwm_tickers = df['Ticker'].dropna().str.strip().tolist()
iwm_tickers = [t for t in iwm_tickers if t and not t.startswith('X')]

# Combine
all_tickers = original + iwm_tickers

# Download
data = yf.download(all_tickers, period='max', interval='1mo', auto_adjust=False)


data['Adj Close'].to_csv('monthly_data.csv')

print(f'Saved monthly_data.csv with {len(data)} months')
