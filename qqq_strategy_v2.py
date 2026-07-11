"""
QQQ Strategy Comparison — 3 Strategies:
1. DCA: $1000/month always
2. Signal V1: Original rules (buy/sell based on 1Y rolling)
3. Signal V2: Improved rules (hold zone, drawdown awareness, 3Y confirmation)

V1 Rules:
  1Y rolling 0% to 20%    -> Buy $1000
  1Y rolling 20% to 40%   -> Sell $1000
  1Y rolling 40% to 60%   -> Sell $2000
  1Y rolling >= 60%       -> Sell $4000
  1Y rolling -20% to 0%   -> Buy $2000
  1Y rolling -40% to -20% -> Buy $3000
  1Y rolling <= -40%      -> Buy $4000

V2 Rules (Improved):
  1Y <= -40%                          -> Buy $4000
  1Y -40% to -20%, drawdown <= -30%   -> Buy $4000 (drawdown boost)
  1Y -40% to -20%, drawdown > -30%    -> Buy $3000
  1Y -20% to 0%                       -> Buy $2000
  1Y 0% to 20%                        -> Buy $1000
  1Y 20% to 30%                       -> HOLD (no action)
  1Y 30% to 40%                       -> Sell $1000
  1Y 40% to 60%, near ATH (dd > -5%)  -> Sell $2000
  1Y 40% to 60%, not near ATH         -> Sell $1000
  1Y >= 60%                           -> Sell $4000
"""

import pandas as pd
import numpy as np
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

# Calculate indicators
df["Rolling_1Y"] = ((df["Price"] / df["Price"].shift(12)) - 1) * 100
df["Rolling_3Y"] = ((df["Price"] / df["Price"].shift(36)) ** (1/3) - 1) * 100
df["Peak"] = df["Price"].cummax()
df["Drawdown"] = (df["Price"] / df["Peak"] - 1) * 100

# Start after we have enough data for all indicators
sim_df = df.dropna(subset=["Rolling_1Y"]).copy().reset_index(drop=True)


def run_strategy(sim_df, strategy_fn, name):
    """Run a strategy and return history dataframe."""
    shares = 0.0
    cash_in = 0.0
    cash_out = 0.0
    history = []

    for _, row in sim_df.iterrows():
        action, amount = strategy_fn(row)

        if action == "buy":
            shares_bought = amount / row["Price"]
            shares += shares_bought
            cash_in += amount
        elif action == "sell":
            shares_to_sell = min(amount / row["Price"], shares)
            actual_sell = shares_to_sell * row["Price"]
            shares -= shares_to_sell
            cash_out += actual_sell
        # else: hold — do nothing

        portfolio_value = shares * row["Price"]
        total_value = portfolio_value + cash_out

        history.append({
            "Date": row["Date"],
            "Action": action,
            "Amount": amount,
            "Shares": shares,
            "Cash_In": cash_in,
            "Cash_Out": cash_out,
            "Portfolio_Value": portfolio_value,
            "Total_Value": total_value,
            "Return_Pct": (total_value / cash_in - 1) * 100 if cash_in > 0 else 0
        })

    return pd.DataFrame(history)


# Strategy 1: Pure DCA
def dca_strategy(row):
    return "buy", 1000

# Strategy 2: Signal V1 (original)
def signal_v1(row):
    r = row["Rolling_1Y"]
    if r <= -40:
        return "buy", 4000
    elif r <= -20:
        return "buy", 3000
    elif r < 0:
        return "buy", 2000
    elif r < 20:
        return "buy", 1000
    elif r < 40:
        return "sell", 1000
    elif r < 60:
        return "sell", 2000
    else:
        return "sell", 4000

# Strategy 3: Signal V2 (improved — buy $500 in hold zone)
def signal_v2(row):
    r = row["Rolling_1Y"]
    dd = row["Drawdown"]

    if r <= -40:
        return "buy", 4000
    elif r <= -20:
        if dd <= -30:
            return "buy", 4000  # drawdown boost
        else:
            return "buy", 3000
    elif r < 0:
        return "buy", 2000
    elif r < 20:
        return "buy", 1000
    elif r < 30:
        return "buy", 500  # light buy — still accumulating during healthy growth
    elif r < 40:
        return "sell", 1000
    elif r < 60:
        if dd > -5:  # near all-time high
            return "sell", 2000
        else:
            return "sell", 1000  # recovering, sell less
    else:  # >= 60%
        return "sell", 4000


# Run all three strategies
dca_df = run_strategy(sim_df, dca_strategy, "DCA")
v1_df = run_strategy(sim_df, signal_v1, "Signal V1")
v2_df = run_strategy(sim_df, signal_v2, "Signal V2")

# ============================================================
# Print Summary
# ============================================================
print("=" * 75)
print("QQQ 3-STRATEGY COMPARISON")
print(f"Period: {sim_df['Date'].min():%B %Y} — {sim_df['Date'].max():%B %Y} ({len(sim_df)} months)")
print("=" * 75)

strategies = [
    ("DCA ($1K/mo)", dca_df),
    ("Signal V1 (Original)", v1_df),
    ("Signal V2 (Improved)", v2_df),
]

print(f"\n{'Metric':<28}{'DCA':>16}{'Signal V1':>16}{'Signal V2':>16}")
print("-" * 76)

for label, sdf in strategies:
    pass

# Print as table
row_data = {
    "Total Cash In": [f"${s['Cash_In'].iloc[-1]:,.0f}" for _, s in strategies],
    "Total Cash Out (sells)": [f"${s['Cash_Out'].iloc[-1]:,.0f}" for _, s in strategies],
    "Current Shares Value": [f"${s['Portfolio_Value'].iloc[-1]:,.0f}" for _, s in strategies],
    "Total Value": [f"${s['Total_Value'].iloc[-1]:,.0f}" for _, s in strategies],
    "Total Return": [f"{s['Return_Pct'].iloc[-1]:.1f}%" for _, s in strategies],
    "Buy Months": [f"{(s['Action']=='buy').sum()}" for _, s in strategies],
    "Sell Months": [f"{(s['Action']=='sell').sum()}" for _, s in strategies],
    "Hold Months": [f"{(s['Action']=='hold').sum()}" for _, s in strategies],
}

for metric, values in row_data.items():
    print(f"{metric:<28}{values[0]:>16}{values[1]:>16}{values[2]:>16}")

# V2 action breakdown
print("\n\nV2 DETAILED ACTION BREAKDOWN:")
print("-" * 50)
v2_actions = v2_df.groupby(["Action", "Amount"]).size().reset_index(name="Count")
v2_actions = v2_actions.sort_values(["Action", "Amount"], ascending=[True, False])
for _, row in v2_actions.iterrows():
    print(f"  {row['Action'].upper():>5} ${row['Amount']:>5,.0f}/mo: {row['Count']:>4} months")

# Outperformance
print("\n\nOUTPERFORMANCE vs DCA:")
print("-" * 50)
dca_final = dca_df["Total_Value"].iloc[-1]
v1_final = v1_df["Total_Value"].iloc[-1]
v2_final = v2_df["Total_Value"].iloc[-1]
dca_return = dca_df["Return_Pct"].iloc[-1]
v1_return = v1_df["Return_Pct"].iloc[-1]
v2_return = v2_df["Return_Pct"].iloc[-1]

print(f"  V1 vs DCA: ${v1_final - dca_final:+,.0f} ({v1_return - dca_return:+.1f}pp)")
print(f"  V2 vs DCA: ${v2_final - dca_final:+,.0f} ({v2_return - dca_return:+.1f}pp)")
print(f"  V2 vs V1:  ${v2_final - v1_final:+,.0f} ({v2_return - v1_return:+.1f}pp)")

# ============================================================
# Build Interactive Chart
# ============================================================
fig = make_subplots(
    rows=3, cols=1,
    shared_xaxes=True,
    vertical_spacing=0.06,
    row_heights=[0.4, 0.35, 0.25],
    subplot_titles=[
        "Total Value Over Time (Portfolio + Cash Out)",
        "Total Return % Over Time",
        "1Y Rolling Return with Strategy Zones"
    ]
)

colors = {"DCA": "blue", "V1": "orange", "V2": "green"}

# Row 1: Total Value
fig.add_trace(go.Scatter(
    x=dca_df["Date"], y=dca_df["Total_Value"],
    mode="lines", name="DCA ($1K/mo)",
    line=dict(color=colors["DCA"], width=2),
    hovertemplate="<b>DCA</b><br>%{x|%b %Y}<br>$%{y:,.0f}<extra></extra>"
), row=1, col=1)

fig.add_trace(go.Scatter(
    x=v1_df["Date"], y=v1_df["Total_Value"],
    mode="lines", name="Signal V1 (Original)",
    line=dict(color=colors["V1"], width=2),
    hovertemplate="<b>V1</b><br>%{x|%b %Y}<br>$%{y:,.0f}<extra></extra>"
), row=1, col=1)

fig.add_trace(go.Scatter(
    x=v2_df["Date"], y=v2_df["Total_Value"],
    mode="lines", name="Signal V2 (Improved)",
    line=dict(color=colors["V2"], width=2.5),
    hovertemplate="<b>V2</b><br>%{x|%b %Y}<br>$%{y:,.0f}<extra></extra>"
), row=1, col=1)

# Cash invested lines
fig.add_trace(go.Scatter(
    x=dca_df["Date"], y=dca_df["Cash_In"],
    mode="lines", name="DCA Cash In",
    line=dict(color=colors["DCA"], width=1, dash="dot"),
    hovertemplate="DCA invested: $%{y:,.0f}<extra></extra>"
), row=1, col=1)

fig.add_trace(go.Scatter(
    x=v2_df["Date"], y=v2_df["Cash_In"],
    mode="lines", name="V2 Cash In",
    line=dict(color=colors["V2"], width=1, dash="dot"),
    hovertemplate="V2 invested: $%{y:,.0f}<extra></extra>"
), row=1, col=1)

# Row 2: Return %
fig.add_trace(go.Scatter(
    x=dca_df["Date"], y=dca_df["Return_Pct"],
    mode="lines", name="DCA %", line=dict(color=colors["DCA"], width=2),
    showlegend=False, hovertemplate="DCA: %{y:.1f}%<extra></extra>"
), row=2, col=1)

fig.add_trace(go.Scatter(
    x=v1_df["Date"], y=v1_df["Return_Pct"],
    mode="lines", name="V1 %", line=dict(color=colors["V1"], width=2),
    showlegend=False, hovertemplate="V1: %{y:.1f}%<extra></extra>"
), row=2, col=1)

fig.add_trace(go.Scatter(
    x=v2_df["Date"], y=v2_df["Return_Pct"],
    mode="lines", name="V2 %", line=dict(color=colors["V2"], width=2.5),
    showlegend=False, hovertemplate="V2: %{y:.1f}%<extra></extra>"
), row=2, col=1)

fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5, row=2, col=1)

# Row 3: Rolling return with zones
fig.add_trace(go.Scatter(
    x=sim_df["Date"], y=sim_df["Rolling_1Y"],
    mode="lines", name="1Y Rolling",
    line=dict(color="gray", width=1.5),
    showlegend=False, hovertemplate="1Y: %{y:.1f}%<extra></extra>"
), row=3, col=1)

# Zone shading
# Buy zone (below 0)
fig.add_hrect(y0=-70, y1=0, fillcolor="green", opacity=0.05, line_width=0, row=3, col=1)
# Hold zone (20-30)
fig.add_hrect(y0=20, y1=30, fillcolor="yellow", opacity=0.1, line_width=0, row=3, col=1)
# Sell zone (above 30)
fig.add_hrect(y0=30, y1=80, fillcolor="red", opacity=0.05, line_width=0, row=3, col=1)

# Threshold lines
for thresh, color, label in [
    (60, "darkred", "Sell $4K"), (40, "red", "Sell $2K"),
    (30, "orange", "Sell $1K (V2)"), (20, "gold", "Hold zone start"),
    (0, "gray", ""), (-20, "lightgreen", "Buy $3K"), (-40, "green", "Buy $4K")
]:
    fig.add_hline(y=thresh, line_dash="dot", line_color=color, opacity=0.6, row=3, col=1)

fig.update_layout(
    height=1050,
    template="plotly_white",
    hovermode="x unified",
    title=dict(
        text="QQQ: DCA vs Signal V1 vs Signal V2 (Improved)",
        font=dict(size=18)
    ),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5)
)

fig.update_yaxes(title_text="Value ($)", row=1, col=1)
fig.update_yaxes(title_text="Return (%)", row=2, col=1)
fig.update_yaxes(title_text="1Y Rolling (%)", row=3, col=1)

# Add range selector
fig.update_xaxes(
    rangeselector=dict(
        buttons=list([
            dict(count=5, label="5Y", step="year", stepmode="backward"),
            dict(count=10, label="10Y", step="year", stepmode="backward"),
            dict(step="all", label="All")
        ])
    ), row=1, col=1
)

output_path = "/Users/ajhanwa/workspace/stocks/qqq_strategy_v2.html"
fig.write_html(output_path, include_plotlyjs="cdn")
print(f"\nChart saved to: {output_path}")
