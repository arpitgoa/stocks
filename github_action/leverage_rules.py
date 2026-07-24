"""
Leverage Rule Checker
=====================
Checks if any of the 4 leverage rules are triggered this month.
Uses a state file (data/prev_signals.json) to track previous months.

Rules (NASDAQ-100 VIX Optimized only, with 70/30 blend):
  1. Exit gold → re-enter stocks: 2x (100% win rate, 7/7)
  2. >10% prev month + month before that green: 2x (67% win rate, 14/21)
  3. Two consecutive >10% months + QQQ > 200 DMA: 2x (73% win rate, 11/15)
  4. After a -10% month: 2x (75% win rate, 12/16)

Combined: 58.0% CAGR / -32.1% MaxDD (vs base 44.1% / -26.8%)
"""

import json
from pathlib import Path
from datetime import datetime

STATE_FILE = Path(__file__).parent / "data" / "prev_signals.json"


def load_state():
    """Load previous month's signal state."""
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {}


def save_state(state):
    """Save current month's state for next run."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def check_leverage_rules(signals, ndx_price=None, ndx_200dma=None):
    """
    Check all 4 leverage rules.
    
    Returns list of triggered rules with details.
    """
    state = load_state()
    triggered = []
    
    # Find the NDX VIX Optimized signal
    ndx_vix = next((s for s in signals if s.get("universe") == "nasdaq100_vix"), None)
    if not ndx_vix:
        return triggered
    
    current_is_gold = ndx_vix.get("go_gold", False)
    prev_was_gold = state.get("was_gold", False)
    prev_return = state.get("prev_return")  # last month's portfolio return %
    prev_prev_return = state.get("prev_prev_return")  # 2 months ago
    
    # Rule 1: Exit gold → re-enter stocks
    if prev_was_gold and not current_is_gold:
        triggered.append({
            "rule": 1,
            "name": "Gold Exit → Stocks",
            "action": "🟢 GO 2x THIS MONTH",
            "confidence": "100% (7/7), avg +13.8%",
            "detail": "Strategy exited gold and re-entering stocks. First month back ALWAYS positive historically.",
        })
    
    # Rule 2: >10% prev month + month before green
    if prev_return is not None and prev_prev_return is not None:
        if prev_return > 10 and prev_prev_return > 0:
            triggered.append({
                "rule": 2,
                "name": ">10% + Prev Green",
                "action": "🟡 CONSIDER 2x (67% win rate)",
                "confidence": "67% (14/21), avg +4.3%",
                "detail": f"Last month: {prev_return:+.1f}%, month before: {prev_prev_return:+.1f}%. Momentum confirmed but lower confidence.",
            })
    
    # Rule 3: Two consecutive >10% months
    if prev_return is not None and prev_prev_return is not None:
        if prev_return > 10 and prev_prev_return > 10:
            triggered.append({
                "rule": 3,
                "name": "Two >10% Months",
                "action": "🟢 GO 2x THIS MONTH",
                "confidence": "73% (11/15), avg +7.0%",
                "detail": f"Last 2 months: {prev_prev_return:+.1f}%, {prev_return:+.1f}%. Epic run — high conviction.",
            })
    
    # Rule 4: After a -10% month
    if prev_return is not None and prev_return < -10:
        triggered.append({
            "rule": 4,
            "name": "Mean Reversion (-10%)",
            "action": "🟢 GO 2x THIS MONTH",
            "confidence": "75% (12/16), avg +7.7%",
            "detail": f"Last month: {prev_return:+.1f}%. Panic washout — bounce expected.",
        })
    
    return triggered


def format_leverage_alerts(triggered_rules):
    """Format leverage alerts for Telegram message."""
    if not triggered_rules:
        return "\n🔕 No leverage rules triggered this month.\n"
    
    lines = [
        "",
        "━━━━━━━━━━━━━━━━━━━━━━",
        f"⚡ <b>LEVERAGE ALERT — {len(triggered_rules)} RULE{'S' if len(triggered_rules) > 1 else ''} TRIGGERED</b>",
        "",
    ]
    
    for rule in triggered_rules:
        lines.append(f"  ⚡ <b>Rule {rule['rule']}: {rule['name']}</b>")
        lines.append(f"     → {rule['action']}")
        lines.append(f"     Win rate: {rule['confidence']}")
        lines.append(f"     {rule['detail']}")
        lines.append("")
    
    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


def update_state(signals, portfolio_return=None):
    """
    Update state file with this month's data for next run.
    """
    state = load_state()
    
    ndx_vix = next((s for s in signals if s.get("universe") == "nasdaq100_vix"), None)
    
    new_state = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "was_gold": ndx_vix.get("go_gold", False) if ndx_vix else False,
        "portfolio": ndx_vix.get("portfolio", []) if ndx_vix else [],
        "prev_prev_return": state.get("prev_return"),
        "prev_return": portfolio_return,
    }
    
    save_state(new_state)
    return new_state
