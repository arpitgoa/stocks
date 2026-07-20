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
from leverage_rules import check_leverage_rules, format_leverage_alerts, update_state


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
    
    # Check leverage rules
    leverage_alerts = check_leverage_rules(signals)
    if leverage_alerts:
        print(f"  ⚡ {len(leverage_alerts)} leverage rule(s) triggered!")
        for alert in leverage_alerts:
            print(f"    Rule {alert['rule']}: {alert['name']} — {alert['confidence']}")
    else:
        print("  No leverage rules triggered.")
    
    message = format_signals_message(signals, constituents)
    
    # Append leverage alerts to message
    leverage_msg = format_leverage_alerts(leverage_alerts)
    if leverage_msg:
        message += leverage_msg
    
    send_telegram(message)
    
    # Update state for next run
    # Calculate this month's approximate return from last month's holdings
    from leverage_rules import load_state
    prev_state = load_state()
    prev_portfolio = prev_state.get("portfolio", [])
    monthly_return = None
    
    if prev_portfolio and prices is not None and not prices.empty:
        # Calculate return of previous holdings over last month
        rets = []
        for ticker in prev_portfolio:
            if ticker in prices.columns:
                ts = prices[ticker].dropna()
                if len(ts) >= 22:
                    month_ret = ts.iloc[-1] / ts.iloc[-22] - 1
                    rets.append(month_ret * 100)
        if rets:
            monthly_return = sum(rets) / len(rets)
            print(f"  📊 Last month's portfolio return (est): {monthly_return:+.1f}%")
    
    update_state(signals, portfolio_return=monthly_return)
    
    print(f"\n{'='*60}")
    print("✅ Pipeline complete.")


if __name__ == "__main__":
    main()
