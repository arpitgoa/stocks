# Automated Monthly Signal Pipeline

Runs on GitHub Actions. Fully automated: fetches index constituents, downloads prices, 
calculates momentum signals, sends Telegram notification.

## Setup

1. **Create a Telegram Bot:**
   - Message @BotFather on Telegram → `/newbot` → get your `BOT_TOKEN`
   - Message your bot, then get your `CHAT_ID` from `https://api.telegram.org/bot<TOKEN>/getUpdates`

2. **Add GitHub Secrets:**
   - Go to your repo → Settings → Secrets and variables → Actions
   - Add: `TELEGRAM_BOT_TOKEN` = your bot token
   - Add: `TELEGRAM_CHAT_ID` = your chat ID

3. **Push this folder to your repo:**
   ```bash
   git add github_action/
   git add .github/workflows/monthly_signal.yml
   git commit -m "Add automated monthly signal pipeline"
   git push
   ```

4. **Done.** It runs automatically on the last trading days of each month at 5 PM ET.

## Manual Trigger

You can also trigger it manually from GitHub → Actions → "Monthly Signal" → "Run workflow"

## Files

```
github_action/
├── fetch_constituents.py   # Scrapes ETF holdings for all index memberships
├── update_prices.py        # Downloads/updates prices from yfinance
├── generate_signals.py     # Runs momentum scoring for all universes
├── send_telegram.py        # Sends notification with picks
├── config.py               # Universe configs + ETF source URLs
├── requirements.txt        # Python dependencies
└── data/                   # Created at runtime
    ├── constituents/       # Current membership CSVs (auto-updated)
    └── prices.parquet      # Rolling 400-day price cache
```
