#!/usr/bin/env python3
"""
Main pipeline script — runs all steps in sequence.
Called by GitHub Actions or manually.

Steps:
1. Fetch latest index constituents
2. Update prices (incremental from yfinance)
3. Generate momentum signals for all universes
4. Send Telegram notification
"""

from datetime import datetime
from fetch_constituents import fetch_all
from update_prices import update_prices
from generate_signals import generate_all_signals
from send_telegram import send_telegram, format_signals_message


def main():
    print("=" * 60)
    print(f"MOMENTUM SIGNAL PIPELINE — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)
    
    # Step 1: Fetch constituents
    print("\n[1/4] Fetching index constituents...")
    constituents = fetch_all()
    
    # Step 2: Update prices
    print("\n[2/4] Updating prices...")
    prices = update_prices()
    
    if prices is None or prices.empty:
        print("❌ No price data available. Aborting.")
        return
    
    # Step 3: Generate signals
    print("\n[3/4] Generating signals...")
    signals = generate_all_signals()
    
    if not signals:
        print("❌ No signals generated. Aborting.")
        return
    
    # Print signals
    print(f"\n{'='*60}")
    print("SIGNALS:")
    print(f"{'='*60}")
    for s in signals:
        if s["go_gold"]:
            print(f"  🟡 {s['label']:<30} GOLD (ratio={s['gold_ratio']:.2f})")
        else:
            print(f"  📈 {s['label']:<30} {', '.join(s['portfolio'])}")
    
    # Step 4: Send Telegram
    print("\n[4/4] Sending notification...")
    message = format_signals_message(signals, constituents)
    send_telegram(message)
    
    print(f"\n{'='*60}")
    print("✅ Pipeline complete.")


if __name__ == "__main__":
    main()
