import pandas as pd
import numpy as np

df = pd.read_csv(
    "~/Downloads/QQQ ETF Stock Price History (2).csv",
    thousands=","
)
df["Date"] = pd.to_datetime(df["Date"], format="%m/%d/%Y")
df = df.sort_values("Date").reset_index(drop=True)
df["Price"] = pd.to_numeric(df["Price"].astype(str).str.replace(",", ""), errors="coerce")
df["Rolling_1Y"] = ((df["Price"] / df["Price"].shift(12)) - 1) * 100
df["Peak"] = df["Price"].cummax()
df["Drawdown"] = (df["Price"] / df["Peak"] - 1) * 100

# Add EMAs (monthly data)
for span in [5, 10, 20, 50]:
    df[f"EMA_{span}"] = df["Price"].ewm(span=span, adjust=False).mean()
    df[f"vs_EMA_{span}"] = (df["Price"] / df[f"EMA_{span}"] - 1) * 100

# Show 2020-2022 with EMAs
print("QQQ WITH EMAs — 2020-2022")
print("=" * 120)
header = f"{'Date':<10}{'Price':>8}{'EMA5':>8}{'EMA10':>8}{'EMA20':>8}{'EMA50':>8}{'vs10':>7}{'vs20':>7}{'vs50':>7}{'1Y Roll':>8}{'DD':>7}"
print(header)
print("-" * 120)

mask = (df["Date"] >= "2020-01-01") & (df["Date"] <= "2022-12-01")
for _, row in df[mask].iterrows():
    r1y = f"{row['Rolling_1Y']:.1f}%" if pd.notna(row["Rolling_1Y"]) else "—"
    print(f"{row['Date'].strftime('%b %Y'):<10}"
          f"{row['Price']:>8.2f}"
          f"{row['EMA_5']:>8.2f}"
          f"{row['EMA_10']:>8.2f}"
          f"{row['EMA_20']:>8.2f}"
          f"{row['EMA_50']:>8.2f}"
          f"{row['vs_EMA_10']:>6.1f}%"
          f"{row['vs_EMA_20']:>6.1f}%"
          f"{row['vs_EMA_50']:>6.1f}%"
          f"{r1y:>8}"
          f"{row['Drawdown']:>6.1f}%")

print()
print()
print("KEY OBSERVATIONS:")
print("=" * 80)

extended = df[df["vs_EMA_50"] > 20]
print(f"Months with Price > 20% above EMA50: {len(extended)} ({len(extended)/len(df)*100:.1f}%)")

below_ema50 = df[df["vs_EMA_50"] < 0]
print(f"Months with Price below EMA50: {len(below_ema50)} ({len(below_ema50)/len(df)*100:.1f}%)")

deep_below = df[df["vs_EMA_50"] < -20]
print(f"Months with Price > 20% below EMA50: {len(deep_below)} ({len(deep_below)/len(df)*100:.1f}%)")

print()
print("DISTRIBUTION: Price vs EMA20 (monthly)")
print("-" * 50)
for low in range(-40, 50, 10):
    high = low + 10
    count = ((df["vs_EMA_20"] >= low) & (df["vs_EMA_20"] < high)).sum()
    if count > 0:
        print(f"  {low:>+3}% to {high:>+3}%: {count:>4} months ({count/len(df)*100:.1f}%)")

print()
print()
# Critical moments
dec21 = df[df["Date"] == "2021-12-01"].iloc[0]
print("DEC 2021 (the top):")
print(f"  Price: ${dec21['Price']:.2f}")
print(f"  vs EMA5:  {dec21['vs_EMA_5']:.1f}%")
print(f"  vs EMA10: {dec21['vs_EMA_10']:.1f}%")
print(f"  vs EMA20: {dec21['vs_EMA_20']:.1f}%")
print(f"  vs EMA50: {dec21['vs_EMA_50']:.1f}%")
print(f"  1Y Rolling: {dec21['Rolling_1Y']:.1f}%")

print()
oct22 = df[df["Date"] == "2022-10-01"].iloc[0]
print("OCT 2022 (the bottom):")
print(f"  Price: ${oct22['Price']:.2f}")
print(f"  vs EMA5:  {oct22['vs_EMA_5']:.1f}%")
print(f"  vs EMA10: {oct22['vs_EMA_10']:.1f}%")
print(f"  vs EMA20: {oct22['vs_EMA_20']:.1f}%")
print(f"  vs EMA50: {oct22['vs_EMA_50']:.1f}%")
print(f"  1Y Rolling: {oct22['Rolling_1Y']:.1f}%")

print()
print()
# Can EMA help with buy sizing?
print("IDEA: Use Price vs EMA20 for buy sizing")
print("=" * 60)
print("Below EMA20 = cheap (buy more), Above EMA20 = expensive (buy less)")
print()
print(f"{'vs EMA20 Range':<20}{'Avg Fwd 6M Ret':>15}{'Months':>8}")
print("-" * 43)
for low in range(-40, 40, 10):
    high = low + 10
    mask2 = (df["vs_EMA_20"] >= low) & (df["vs_EMA_20"] < high)
    subset = df[mask2].copy()
    # Forward 6 month return
    fwd = []
    for idx in subset.index:
        if idx + 6 < len(df):
            fwd.append((df.loc[idx + 6, "Price"] / df.loc[idx, "Price"] - 1) * 100)
    if len(fwd) > 5:
        print(f"  {low:>+3}% to {high:>+3}%       {np.mean(fwd):>10.1f}%    {len(fwd):>5}")
