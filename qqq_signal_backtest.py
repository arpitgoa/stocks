"""
QQQ 1Y Rolling Return Signal Backtest
Tests the strategy: sell when 1Y rolling > 40%, buy when 1Y rolling < -20%
Analyzes forward returns after each signal to see if the thesis holds.
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

# Forward returns (what happens AFTER the signal)
for fwd in [3, 6, 12, 24, 36]:
    df[f"Fwd_{fwd}m"] = ((df["Price"].shift(-fwd) / df["Price"]) - 1) * 100

# Identify signals
sell_threshold = 40
buy_threshold = -20

df["Signal"] = "Hold"
df.loc[df["Rolling_1Y"] >= sell_threshold, "Signal"] = "Sell"
df.loc[df["Rolling_1Y"] <= buy_threshold, "Signal"] = "Buy"

# Analyze forward returns by signal
print("=" * 70)
print("QQQ 1Y ROLLING RETURN SIGNAL ANALYSIS")
print(f"Sell signal: 1Y return >= {sell_threshold}%")
print(f"Buy signal:  1Y return <= {buy_threshold}%")
print("=" * 70)

for signal in ["Buy", "Sell", "Hold"]:
    subset = df[df["Signal"] == signal].dropna(subset=["Rolling_1Y"])
    print(f"\n{'─' * 70}")
    print(f"  {signal.upper()} SIGNALS: {len(subset)} occurrences")
    print(f"{'─' * 70}")
    print(f"  {'Forward Period':<18}{'Avg Return':>12}{'Median':>10}{'Win Rate':>10}{'Min':>10}{'Max':>10}")
    print(f"  {'-'*68}")
    for fwd, label in [(3, "3 months"), (6, "6 months"), (12, "1 year"), (24, "2 years"), (36, "3 years")]:
        col = f"Fwd_{fwd}m"
        valid = subset.dropna(subset=[col])
        if len(valid) > 0:
            avg = valid[col].mean()
            med = valid[col].median()
            win = (valid[col] > 0).mean() * 100
            mn = valid[col].min()
            mx = valid[col].max()
            print(f"  {label:<18}{avg:>10.1f}%{med:>9.1f}%{win:>9.0f}%{mn:>9.1f}%{mx:>9.1f}%")

# Build visualization
fig = make_subplots(
    rows=2, cols=1,
    shared_xaxes=True,
    vertical_spacing=0.08,
    row_heights=[0.6, 0.4],
    subplot_titles=["QQQ Price with Buy/Sell Signals", "1Y Rolling Return with Thresholds"]
)

# Price chart with signals
fig.add_trace(go.Scatter(
    x=df["Date"], y=df["Price"],
    mode="lines", name="QQQ Price",
    line=dict(color="gray", width=1.5)
), row=1, col=1)

buy_signals = df[df["Signal"] == "Buy"]
sell_signals = df[df["Signal"] == "Sell"]

fig.add_trace(go.Scatter(
    x=buy_signals["Date"], y=buy_signals["Price"],
    mode="markers", name=f"Buy (1Y ≤ {buy_threshold}%)",
    marker=dict(color="green", size=10, symbol="triangle-up")
), row=1, col=1)

fig.add_trace(go.Scatter(
    x=sell_signals["Date"], y=sell_signals["Price"],
    mode="markers", name=f"Sell (1Y ≥ {sell_threshold}%)",
    marker=dict(color="red", size=10, symbol="triangle-down")
), row=1, col=1)

# Rolling return with thresholds
fig.add_trace(go.Scatter(
    x=df["Date"], y=df["Rolling_1Y"],
    mode="lines", name="1Y Rolling Return",
    line=dict(color="royalblue", width=1.5),
    showlegend=False
), row=2, col=1)

fig.add_hline(y=sell_threshold, line_dash="dash", line_color="red",
              annotation_text=f"Sell ({sell_threshold}%)", row=2, col=1)
fig.add_hline(y=buy_threshold, line_dash="dash", line_color="green",
              annotation_text=f"Buy ({buy_threshold}%)", row=2, col=1)
fig.add_hline(y=0, line_dash="dot", line_color="gray", opacity=0.5, row=2, col=1)

# Shade zones
rolling_valid = df.dropna(subset=["Rolling_1Y"])
fig.add_trace(go.Scatter(
    x=rolling_valid["Date"],
    y=rolling_valid["Rolling_1Y"].clip(lower=sell_threshold),
    fill="tozeroy",
    mode="none",
    fillcolor="rgba(220, 53, 69, 0.1)",
    showlegend=False,
    hoverinfo="skip"
), row=2, col=1)

fig.update_layout(
    height=800,
    template="plotly_white",
    hovermode="x unified",
    title=dict(
        text="QQQ Signal Analysis: Buy below -20% | Sell above +40% (1Y Rolling)",
        font=dict(size=16)
    ),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5)
)

fig.update_yaxes(title_text="Price ($)", row=1, col=1)
fig.update_yaxes(title_text="1Y Return (%)", row=2, col=1)

output_path = "/Users/ajhanwa/workspace/stocks/qqq_signal_backtest.html"
fig.write_html(output_path, include_plotlyjs="cdn")
print(f"\nChart saved to: {output_path}")
