"""
Send signal notification via Telegram.
Requires TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID environment variables.
"""

import os
import requests
from datetime import datetime
from config import LEVERAGED_ETF_MAP


def send_telegram(message, bot_token=None, chat_id=None):
    """Send a message via Telegram bot."""
    token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = chat_id or os.environ.get("TELEGRAM_CHAT_ID")
    
    if not token or not chat:
        print("⚠️ Telegram credentials not set. Message:")
        print(message)
        return False
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat,
        "text": message,
        "parse_mode": "HTML",
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print("✅ Telegram message sent")
            return True
        else:
            print(f"❌ Telegram error: {response.status_code} {response.text}")
            return False
    except Exception as e:
        print(f"❌ Telegram failed: {e}")
        return False


def format_signals_message(signals, constituent_sources=None):
    """Format signals into a readable Telegram message."""
    date_str = datetime.now().strftime("%Y-%m-%d")
    
    lines = [f"<b>📊 Monthly Momentum Signals</b>", f"<i>Date: {date_str}</i>", ""]
    
    for s in signals:
        label = s["label"]
        ratio_str = f" ({s['gold_ratio']:.2f}/{s['gold_threshold']})" if s.get('gold_ratio') else ""
        if s["go_gold"]:
            lines.append(f"🟡 <b>{label}</b>: GOLD{ratio_str}")
        else:
            stocks = ", ".join(s["portfolio"])
            lev = ", ".join(s["leveraged"])
            lines.append(f"📈 <b>{label}</b>: {stocks}{ratio_str}")
            if lev != stocks:
                lines.append(f"    <i>Lev: {lev}</i>")
    
    # Add VIX
    vix_signal = next((s for s in signals if s.get("vix")), None)
    if vix_signal:
        lines.append(f"\nVIX: {vix_signal['vix']:.1f}")
    
    # Add data source info
    if constituent_sources:
        live = [k for k, v in constituent_sources.items() if v.get("source") == "live"]
        cached = [k for k, v in constituent_sources.items() if v.get("source") == "cached"]
        lines.append("")
        if live:
            lines.append(f"✅ Live data: {', '.join(live)}")
        if cached:
            lines.append(f"⚠️ Cached data: {', '.join(cached)}")
    
    return "\n".join(lines)


if __name__ == "__main__":
    # Test with sample data
    test_signals = [
        {"label": "NASDAQ-100 VIX", "go_gold": True, "gold_ratio": 7.24, "vix": 16.7, "portfolio": [], "leveraged": []},
        {"label": "S&P 500", "go_gold": False, "gold_ratio": 1.84, "vix": 16.7, "portfolio": ["MU", "WDC", "STX"], "leveraged": ["MUU", "WDC", "STX"]},
    ]
    msg = format_signals_message(test_signals)
    send_telegram(msg)
