# Stock Logos

Cached stock logos for the TradingView overlay userscript.

## Setup

1. Run `python bulk_download.py` to download logos for all tickers in your universe
2. Push this repo to GitHub: `https://github.com/ajhanwa/stock-logos`
3. The TradingView userscript fetches from this repo first (free, fast, portable)

## Structure

```
stock-logos/
├── logos/          # PNG files named by ticker (AAPL.png, TSLA.png, etc.)
├── bulk_download.py
├── README.md
└── .gitignore
```

## Adding new tickers

```bash
python bulk_download.py --tickers NVDA,AMD,PLTR
```

Or re-run without args to download the full universe.
