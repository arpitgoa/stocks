"""
QQQ Rolling Returns — Interactive Chart (1, 3, 5, 10, 20 Years)
Reads QQQ monthly price data and produces an interactive Plotly HTML chart
showing annualized rolling returns for multiple time horizons.
"""

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Load data
df = pd.read_csv(
    "~/Downloads/QQQ ETF Stock Price History (2).csv",
    thousands=","
)

# Parse date and sort chronologically
df["Date"] = pd.to_datetime(df["Date"], format="%m/%d/%Y")
df = df.sort_values("Date").reset_index(drop=True)

# Clean Price column
df["Price"] = pd.to_numeric(df["Price"].astype(str).str.replace(",", ""), errors="coerce")

# Define rolling periods
periods = {
    "1Y": 12,
    "3Y": 36,
    "5Y": 60,
    "10Y": 120,
    "20Y": 240,
}

colors = {
    "1Y": "#ff7f0e",   # orange
    "3Y": "#2ca02c",   # green
    "5Y": "#1f77b4",   # blue
    "10Y": "#9467bd",  # purple
    "20Y": "#d62728",  # red
}

# Calculate rolling returns for each period
for label, months in periods.items():
    years = months / 12
    df[f"Price_{months}m_ago"] = df["Price"].shift(months)
    df[f"Rolling_{label}"] = ((df["Price"] / df[f"Price_{months}m_ago"]) ** (1 / years) - 1) * 100

# Build interactive chart
fig = go.Figure()

for label, months in periods.items():
    col = f"Rolling_{label}"
    subset = df.dropna(subset=[col])
    fig.add_trace(go.Scatter(
        x=subset["Date"],
        y=subset[col],
        mode="lines",
        name=f"{label} Annualized",
        line=dict(color=colors[label], width=2),
        hovertemplate=f"<b>%{{x|%b %Y}}</b><br>{label} Return: %{{y:.2f}}%<extra></extra>"
    ))

# Zero line
fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.6)

# Build summary annotation
summary_parts = []
for label in periods:
    col = f"Rolling_{label}"
    subset = df.dropna(subset=[col])
    if len(subset) > 0:
        summary_parts.append(
            f"{label}: avg {subset[col].mean():.1f}% "
            f"(min {subset[col].min():.1f}%, max {subset[col].max():.1f}%)"
        )

fig.update_layout(
    title=dict(
        text="QQQ — Monthly Rolling Annualized Returns (1Y, 3Y, 5Y, 10Y, 20Y)",
        font=dict(size=18)
    ),
    xaxis_title="Date",
    yaxis_title="Annualized Return (%)",
    template="plotly_white",
    hovermode="x unified",
    height=650,
    margin=dict(l=60, r=30, t=80, b=100),
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="center",
        x=0.5
    ),
    annotations=[
        dict(
            text="<br>".join(summary_parts),
            xref="paper", yref="paper",
            x=0.5, y=-0.18,
            showarrow=False,
            font=dict(size=11, color="gray"),
            align="center"
        )
    ]
)

# Add range selector buttons
fig.update_xaxes(
    rangeselector=dict(
        buttons=list([
            dict(count=5, label="5Y", step="year", stepmode="backward"),
            dict(count=10, label="10Y", step="year", stepmode="backward"),
            dict(count=20, label="20Y", step="year", stepmode="backward"),
            dict(step="all", label="All")
        ])
    )
)

# Save interactive HTML
output_path = "/Users/ajhanwa/workspace/stocks/qqq_5y_rolling_return.html"
fig.write_html(output_path, include_plotlyjs="cdn")
print(f"Chart saved to: {output_path}")
print(f"\nSummary Statistics:")
print(f"{'Period':<8}{'Avg':>8}{'Min':>8}{'Max':>8}{'Obs':>6}")
print("-" * 38)
for label in periods:
    col = f"Rolling_{label}"
    subset = df.dropna(subset=[col])
    if len(subset) > 0:
        print(f"{label:<8}{subset[col].mean():>7.1f}%{subset[col].min():>7.1f}%{subset[col].max():>7.1f}%{len(subset):>6}")
