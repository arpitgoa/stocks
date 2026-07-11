"""
QQQ Strategy Comparison:
1. DCA: Invest $1000/month no matter what
2. Signal-Based: Vary buy/sell amount based on 1Y rolling return

Rules for Signal Strategy:
  1Y rolling 0% to 20%    -> Buy $1000/month
  1Y rolling 20% to 40%   -> Sell $1000/month
  1Y rolling 40% to 60%   -> Sell $2000/month
  1Y rolling >= 60%       -> Sell $4000/month
  1Y rolling -20% to 0%   -> Buy $2000/month
  1Y rolling -40% to -20% -> Buy $3000/month
  1Y rolling <= -40%      -> Buy $4000/month
"""

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Load data
df = pd.read_csv(
    "~/Downloads/QQQ ETF Stock Price History (2).csv",
    thousands=","
)
df["Date"] = pd.to_datetime(df["Date"], format="%m/%d/%Y")
df = df.sort_values("Date").reset_index(drop=True)
df["Price"] = pd.to_numeric(df["Price"].astype(str).str.replace(",", ""), errors="coerce")

# Calculate 1Y rolling return
df["Rolling_1Y"] = ((df["Price"] / df["Price"].shift(12)) - 1) * 100

# Start simulation after we have 12 months of data for rolling calc
sim_df = df.dropna(subset=["Rolling_1Y"]).copy().reset_index(drop=True)

# ============================================================
# Strategy 1: Pure DCA — $1000/month always
# ============================================================
dca_shares = 0.0
dca_cash_invested = 0.0
dca_history = []

for _, row in sim_df.iterrows():
    shares_bought = 1000 / row["Price"]
    dca_shares += shares_bought
    dca_cash_invested += 1000
    portfolio_value = dca_shares * row["Price"]
    dca_history.append({
        "Date": row["Date"],
        "Shares": dca_shares,
        "Cash_Invested": dca_cash_invested,
        "Portfolio_Value": portfolio_value,
        "Gain": portfolio_value - dca_cash_invested,
        "Return_Pct": (portfolio_value / dca_cash_invested - 1) * 100
    })

dca_df = pd.DataFrame(dca_history)

# ============================================================
# Strategy 2: Signal-based
# ============================================================
sig_shares = 0.0
sig_cash_invested = 0.0  # net cash put in (buys - sells)
sig_cash_out = 0.0       # total cash withdrawn from sells
sig_cash_in = 0.0        # total cash invested from buys
sig_history = []

for _, row in sim_df.iterrows():
    r = row["Rolling_1Y"]

    # Determine action and amount
    if r <= -40:
        action, amount = "buy", 4000
    elif r <= -20:
        action, amount = "buy", 3000
    elif r < 0:
        action, amount = "buy", 2000
    elif r < 20:
        action, amount = "buy", 1000
    elif r < 40:
        action, amount = "sell", 1000
    elif r < 60:
        action, amount = "sell", 2000
    else:  # >= 60
        action, amount = "sell", 4000

    if action == "buy":
        shares_bought = amount / row["Price"]
        sig_shares += shares_bought
        sig_cash_in += amount
        sig_cash_invested += amount
    else:  # sell
        # Can only sell what we have
        shares_to_sell = min(amount / row["Price"], sig_shares)
        actual_sell_value = shares_to_sell * row["Price"]
        sig_shares -= shares_to_sell
        sig_cash_out += actual_sell_value
        sig_cash_invested -= actual_sell_value

    portfolio_value = sig_shares * row["Price"]
    total_value = portfolio_value + sig_cash_out  # shares + all cash taken out

    sig_history.append({
        "Date": row["Date"],
        "Rolling_1Y": r,
        "Action": action,
        "Amount": amount,
        "Shares": sig_shares,
        "Cash_In": sig_cash_in,
        "Cash_Out": sig_cash_out,
        "Net_Invested": sig_cash_invested,
        "Portfolio_Value": portfolio_value,
        "Total_Value": total_value,  # portfolio + withdrawn cash
        "Return_Pct": (total_value / sig_cash_in - 1) * 100 if sig_cash_in > 0 else 0
    })

sig_df = pd.DataFrame(sig_history)

# ============================================================
# Print Summary
# ============================================================
print("=" * 70)
print("QQQ STRATEGY COMPARISON")
print(f"Period: {sim_df['Date'].min():%B %Y} — {sim_df['Date'].max():%B %Y} ({len(sim_df)} months)")
print("=" * 70)

print("\n📊 STRATEGY 1: Pure DCA ($1,000/month)")
print("-" * 50)
print(f"  Total Invested:      ${dca_df['Cash_Invested'].iloc[-1]:>12,.0f}")
print(f"  Portfolio Value:     ${dca_df['Portfolio_Value'].iloc[-1]:>12,.0f}")
print(f"  Total Gain:          ${dca_df['Gain'].iloc[-1]:>12,.0f}")
print(f"  Total Return:        {dca_df['Return_Pct'].iloc[-1]:>11.1f}%")

print("\n📊 STRATEGY 2: Signal-Based (Variable Buy/Sell)")
print("-" * 50)
print(f"  Total Cash Put In:   ${sig_df['Cash_In'].iloc[-1]:>12,.0f}")
print(f"  Total Cash Taken Out:${sig_df['Cash_Out'].iloc[-1]:>12,.0f}")
print(f"  Current Shares Value:${sig_df['Portfolio_Value'].iloc[-1]:>12,.0f}")
print(f"  Total Value (shares + cash out): ${sig_df['Total_Value'].iloc[-1]:>12,.0f}")
print(f"  Total Return:        {sig_df['Return_Pct'].iloc[-1]:>11.1f}%")
print(f"  Net Cash Still Invested: ${sig_df['Net_Invested'].iloc[-1]:>12,.0f}")

# Buy/sell breakdown
buy_months = (sig_df["Action"] == "buy").sum()
sell_months = (sig_df["Action"] == "sell").sum()
print(f"\n  Buy months: {buy_months} | Sell months: {sell_months}")

print("\n📊 COMPARISON")
print("-" * 50)
dca_final = dca_df["Portfolio_Value"].iloc[-1]
sig_final = sig_df["Total_Value"].iloc[-1]
dca_invested = dca_df["Cash_Invested"].iloc[-1]
sig_invested = sig_df["Cash_In"].iloc[-1]
print(f"  DCA invested ${dca_invested:,.0f} -> worth ${dca_final:,.0f} ({dca_df['Return_Pct'].iloc[-1]:.1f}% return)")
print(f"  Signal invested ${sig_invested:,.0f} -> worth ${sig_final:,.0f} ({sig_df['Return_Pct'].iloc[-1]:.1f}% return)")
print(f"  Difference in total value: ${sig_final - dca_final:+,.0f}")
print(f"  Difference in return %:    {sig_df['Return_Pct'].iloc[-1] - dca_df['Return_Pct'].iloc[-1]:+.1f}pp")

# ============================================================
# Build Interactive Chart
# ============================================================
fig = make_subplots(
    rows=3, cols=1,
    shared_xaxes=True,
    vertical_spacing=0.06,
    row_heights=[0.4, 0.35, 0.25],
    subplot_titles=[
        "Portfolio Value Over Time",
        "Total Return % Over Time",
        "1Y Rolling Return & Actions"
    ]
)

# Row 1: Portfolio Value
fig.add_trace(go.Scatter(
    x=dca_df["Date"], y=dca_df["Portfolio_Value"],
    mode="lines", name="DCA ($1K/mo)",
    line=dict(color="blue", width=2),
    hovertemplate="<b>DCA</b><br>%{x|%b %Y}<br>Value: $%{y:,.0f}<extra></extra>"
), row=1, col=1)

fig.add_trace(go.Scatter(
    x=sig_df["Date"], y=sig_df["Total_Value"],
    mode="lines", name="Signal Strategy",
    line=dict(color="green", width=2),
    hovertemplate="<b>Signal</b><br>%{x|%b %Y}<br>Value: $%{y:,.0f}<extra></extra>"
), row=1, col=1)

fig.add_trace(go.Scatter(
    x=dca_df["Date"], y=dca_df["Cash_Invested"],
    mode="lines", name="DCA Cash In",
    line=dict(color="gray", width=1, dash="dot"),
    hovertemplate="<b>DCA Cash In</b><br>$%{y:,.0f}<extra></extra>"
), row=1, col=1)

fig.add_trace(go.Scatter(
    x=sig_df["Date"], y=sig_df["Cash_In"],
    mode="lines", name="Signal Cash In",
    line=dict(color="orange", width=1, dash="dot"),
    hovertemplate="<b>Signal Cash In</b><br>$%{y:,.0f}<extra></extra>"
), row=1, col=1)

# Row 2: Return %
fig.add_trace(go.Scatter(
    x=dca_df["Date"], y=dca_df["Return_Pct"],
    mode="lines", name="DCA Return %",
    line=dict(color="blue", width=2),
    showlegend=False,
    hovertemplate="DCA: %{y:.1f}%<extra></extra>"
), row=2, col=1)

fig.add_trace(go.Scatter(
    x=sig_df["Date"], y=sig_df["Return_Pct"],
    mode="lines", name="Signal Return %",
    line=dict(color="green", width=2),
    showlegend=False,
    hovertemplate="Signal: %{y:.1f}%<extra></extra>"
), row=2, col=1)

fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5, row=2, col=1)

# Row 3: Rolling return with colored zones
fig.add_trace(go.Scatter(
    x=sig_df["Date"], y=sig_df["Rolling_1Y"],
    mode="lines", name="1Y Rolling",
    line=dict(color="gray", width=1.5),
    showlegend=False,
    hovertemplate="1Y Rolling: %{y:.1f}%<extra></extra>"
), row=3, col=1)

# Add threshold lines
for thresh, color, label in [
    (60, "darkred", "Sell $4K"), (40, "red", "Sell $2K"), (20, "orange", "Sell $1K"),
    (0, "gray", ""), (-20, "lightgreen", "Buy $4K"), (-40, "green", "Buy $8K")
]:
    fig.add_hline(y=thresh, line_dash="dot", line_color=color, opacity=0.5, row=3, col=1)

fig.update_layout(
    height=1000,
    template="plotly_white",
    hovermode="x unified",
    title=dict(
        text="QQQ: DCA vs Signal-Based Strategy Comparison",
        font=dict(size=18)
    ),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5)
)

fig.update_yaxes(title_text="Value ($)", row=1, col=1)
fig.update_yaxes(title_text="Return (%)", row=2, col=1)
fig.update_yaxes(title_text="1Y Rolling (%)", row=3, col=1)

output_path = "/Users/ajhanwa/workspace/stocks/qqq_strategy_comparison.html"
fig.write_html(output_path, include_plotlyjs="cdn")
print(f"\nChart saved to: {output_path}")
