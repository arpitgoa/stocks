"""
build_comparison_dashboard.py

Downloads ETF data via yfinance, reads the NDX Momentum backtest CSV,
computes yearly returns (2009–2026 YTD), and generates a single-file
comparison HTML dashboard.
"""

import os
import json
import math
import datetime
import warnings

import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")

# ── Configuration ──────────────────────────────────────────────────────────────
OUTPUT_HTML = "/Users/ajhanwa/Documents/workspace/stocks/nasdaq_momentum/dashboards/comparison.html"
BACKTEST_CSV = "/Users/ajhanwa/Documents/workspace/stocks/nasdaq_momentum/dashboards/nasdaq100_vix/backtest_wide.csv"

ETF_TICKERS = ["SPMO", "QQQ", "SPY", "IWM", "TQQQ", "UPRO", "TNA", "XMMO", "XSMO"]
STRATEGY_LABEL = "NDX Momentum"
START_DATE = "2008-01-01"
YEARS = list(range(2009, 2027))   # 2026 = YTD


# ── 1. Download ETF prices ─────────────────────────────────────────────────────
def download_etfs(tickers, start):
    print("Downloading ETF data from yfinance …")
    raw = yf.download(tickers, start=start, auto_adjust=True, progress=False)
    close = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw
    close = close[tickers]  # keep column order
    close.index = pd.to_datetime(close.index)
    return close


# ── 2. Compute yearly returns from daily prices ───────────────────────────────
def yearly_returns_from_prices(close_df):
    """Returns a dict:  ticker -> {year: pct_return}"""
    results = {}
    for ticker in close_df.columns:
        series = close_df[ticker].dropna()
        yr_ret = {}
        for yr in YEARS:
            if yr == datetime.date.today().year:
                # YTD: start of year to latest available
                yr_data = series[series.index.year == yr]
                prior = series[series.index.year == yr - 1]
                if yr_data.empty or prior.empty:
                    continue
                start_px = prior.iloc[-1]
                end_px = yr_data.iloc[-1]
            else:
                yr_data = series[series.index.year == yr]
                prior = series[series.index.year == yr - 1]
                if yr_data.empty or prior.empty:
                    continue
                start_px = prior.iloc[-1]
                end_px = yr_data.iloc[-1]
            if start_px > 0:
                yr_ret[yr] = round((end_px / start_px - 1) * 100, 2)
        results[ticker] = yr_ret
    return results


# ── 3. Read strategy CSV and compute yearly returns ───────────────────────────
def strategy_yearly_returns(csv_path):
    df = pd.read_csv(csv_path, parse_dates=["End_Date"])
    df["year"] = df["End_Date"].dt.year
    # Compound monthly returns within each year
    df["growth"] = 1 + df["Portfolio_Return_Pct"] / 100
    yr_ret = {}
    for yr, grp in df.groupby("year"):
        if yr in YEARS:
            compound = grp["growth"].prod() - 1
            yr_ret[yr] = round(compound * 100, 2)
    return yr_ret


# ── 4. Summary statistics ──────────────────────────────────────────────────────
def summary_stats(close_df, etf_yr_rets, strat_yr_ret, strat_label):
    stats = []

    for ticker in close_df.columns:
        series = close_df[ticker].dropna()
        if series.empty:
            continue
        inception = series.index[0].strftime("%Y-%m-%d")
        total_years = (series.index[-1] - series.index[0]).days / 365.25
        total_ret = series.iloc[-1] / series.iloc[0] - 1
        cagr = (1 + total_ret) ** (1 / total_years) - 1 if total_years > 0 else 0

        # Max drawdown
        roll_max = series.cummax()
        dd = (series - roll_max) / roll_max
        max_dd = dd.min()

        # Sharpe (annualised, risk-free ≈ 0 for simplicity)
        daily_ret = series.pct_change().dropna()
        sharpe = (daily_ret.mean() / daily_ret.std() * math.sqrt(252)
                  if daily_ret.std() > 0 else 0)

        yr_vals = list(etf_yr_rets.get(ticker, {}).values())
        best = max(yr_vals) if yr_vals else None
        worst = min(yr_vals) if yr_vals else None

        stats.append({
            "ticker": ticker,
            "inception": inception,
            "cagr": round(cagr * 100, 1),
            "max_dd": round(max_dd * 100, 1),
            "sharpe": round(sharpe, 2),
            "best": best,
            "worst": worst,
        })

    # Strategy stats (from yearly returns only)
    yr_vals = list(strat_yr_ret.values())
    if yr_vals:
        n = len(yr_vals)
        cagr_strat = ((1 + sum(yr_vals) / 100 / n) ** 1 - 1) * 100  # simple avg approximation
        # Better: compound
        compound = 1
        for v in yr_vals:
            compound *= (1 + v / 100)
        cagr_strat = round((compound ** (1 / n) - 1) * 100, 1)
        # Max DD not easily computed without daily data, skip
        stats.append({
            "ticker": strat_label,
            "inception": "2008",
            "cagr": cagr_strat,
            "max_dd": "—",
            "sharpe": "—",
            "best": round(max(yr_vals), 1),
            "worst": round(min(yr_vals), 1),
        })

    return stats


# ── 5. Build growth-of-$10k series ────────────────────────────────────────────
def growth_series(close_df, etf_yr_rets, strat_yr_ret, strat_label):
    """Returns {ticker: {year: value}} starting at 10000."""
    all_series = {}

    for ticker in close_df.columns:
        yr_rets = etf_yr_rets.get(ticker, {})
        val = 10000.0
        series = {}
        for yr in YEARS:
            if yr in yr_rets:
                val *= (1 + yr_rets[yr] / 100)
                series[yr] = round(val, 2)
        if series:
            all_series[ticker] = series

    # Strategy
    val = 10000.0
    series = {}
    for yr in YEARS:
        if yr in strat_yr_ret:
            val *= (1 + strat_yr_ret[yr] / 100)
            series[yr] = round(val, 2)
    if series:
        all_series[strat_label] = series

    return all_series


# ── 6. Helpers ─────────────────────────────────────────────────────────────────
PALETTE = [
    "#2196F3", "#FF5722", "#4CAF50", "#9C27B0", "#FF9800",
    "#00BCD4", "#F44336", "#8BC34A", "#3F51B5", "#E91E63",
]

def cell_color(val):
    if val is None:
        return "#333", "#888"
    if val > 50:
        return "#1B5E20", "#E8F5E9"
    if val > 20:
        return "#2E7D32", "#C8E6C9"
    if val > 0:
        return "#388E3C", "#DCEDC8"
    if val > -20:
        return "#B71C1C", "#FFCDD2"
    return "#7F0000", "#EF9A9A"


# ── 7. Generate HTML ───────────────────────────────────────────────────────────
def build_html(stats, etf_yr_rets, strat_yr_ret, strat_label, growth_data):
    all_tickers_order = ETF_TICKERS + [strat_label]

    # ── Merge all returns into one dict keyed by label ────────────────────
    all_yr_rets = dict(etf_yr_rets)
    all_yr_rets[strat_label] = strat_yr_ret

    # ── Determine best performer per year (for bold in heatmap) ──────────
    best_per_year = {}
    for yr in YEARS:
        candidates = {t: all_yr_rets[t][yr] for t in all_tickers_order if yr in all_yr_rets.get(t, {})}
        if candidates:
            best_per_year[yr] = max(candidates, key=candidates.get)

    # ── JSON payloads for Chart.js ─────────────────────────────────────────
    years_js = json.dumps(YEARS)

    # Grouped bar chart datasets
    bar_datasets = []
    for i, ticker in enumerate(all_tickers_order):
        yr_rets = all_yr_rets.get(ticker, {})
        data_points = [yr_rets.get(yr) for yr in YEARS]  # None → null in JS
        color = PALETTE[i % len(PALETTE)]
        bar_datasets.append({
            "label": ticker,
            "data": data_points,
            "backgroundColor": color,
            "borderColor": color,
            "borderWidth": 1,
        })
    bar_datasets_js = json.dumps(bar_datasets)

    # Line chart datasets (growth)
    line_datasets = []
    for i, ticker in enumerate(all_tickers_order):
        gdata = growth_data.get(ticker, {})
        data_points = [gdata.get(yr) for yr in YEARS]
        color = PALETTE[i % len(PALETTE)]
        is_strat = ticker == strat_label
        line_datasets.append({
            "label": ticker,
            "data": data_points,
            "borderColor": color,
            "backgroundColor": "transparent",
            "borderWidth": 3 if is_strat else 1.5,
            "borderDash": [6, 3] if is_strat else [],
            "pointRadius": 3,
            "tension": 0.1,
        })
    line_datasets_js = json.dumps(line_datasets)

    # ── Summary table rows ─────────────────────────────────────────────────
    def fmt(v, suffix=""):
        if v == "—" or v is None:
            return "—"
        return f"{v}{suffix}"

    summary_rows = ""
    for s in stats:
        best_str = f"+{s['best']}%" if s["best"] is not None and s["best"] != "—" else "—"
        worst_str = f"{s['worst']}%" if s["worst"] is not None and s["worst"] != "—" else "—"
        cagr_str = fmt(s["cagr"], "%")
        dd_str = fmt(s["max_dd"], "%") if s["max_dd"] != "—" else "—"
        sharpe_str = fmt(s["sharpe"]) if s["sharpe"] != "—" else "—"
        highlight = ' class="strategy-row"' if s["ticker"] == strat_label else ""
        summary_rows += f"""
        <tr{highlight}>
          <td><strong>{s['ticker']}</strong></td>
          <td>{s['inception']}</td>
          <td>{cagr_str}</td>
          <td>{dd_str}</td>
          <td>{sharpe_str}</td>
          <td style="color:#388E3C">{best_str}</td>
          <td style="color:#B71C1C">{worst_str}</td>
        </tr>"""

    # ── Heatmap rows ──────────────────────────────────────────────────────
    heatmap_header = "".join(f'<th>{t}</th>' for t in all_tickers_order)
    heatmap_rows = ""
    for yr in YEARS:
        ytd_marker = " <span class='ytd'>YTD</span>" if yr == datetime.date.today().year else ""
        row = f"<tr><td><strong>{yr}</strong>{ytd_marker}</td>"
        for ticker in all_tickers_order:
            val = all_yr_rets.get(ticker, {}).get(yr)
            if val is None:
                row += '<td class="na">—</td>'
            else:
                text_color, bg_color = cell_color(val)
                sign = "+" if val > 0 else ""
                is_best = best_per_year.get(yr) == ticker
                bold_open = "<strong>" if is_best else ""
                bold_close = "</strong>" if is_best else ""
                row += (f'<td style="background:{bg_color};color:{text_color}">'
                        f'{bold_open}{sign}{val:.1f}%{bold_close}</td>')
        row += "</tr>"
        heatmap_rows += row

    # ── Full HTML ──────────────────────────────────────────────────────────
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>ETF vs NDX Momentum — Yearly Returns Dashboard</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js"></script>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: #0f1117;
      color: #e0e0e0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      font-size: 13px;
      padding: 24px;
    }}
    h1 {{ font-size: 22px; font-weight: 700; margin-bottom: 4px; color: #fff; }}
    .subtitle {{ color: #888; margin-bottom: 32px; font-size: 12px; }}
    h2 {{ font-size: 15px; font-weight: 600; margin: 32px 0 12px; color: #ccc;
          text-transform: uppercase; letter-spacing: 0.05em; }}
    .card {{
      background: #1a1d27;
      border: 1px solid #2a2d3a;
      border-radius: 8px;
      padding: 20px;
      margin-bottom: 28px;
      overflow-x: auto;
    }}
    /* Summary table */
    table.summary {{ width: 100%; border-collapse: collapse; }}
    table.summary th {{
      text-align: left; padding: 8px 12px;
      border-bottom: 2px solid #333;
      color: #aaa; font-weight: 600; font-size: 11px;
      text-transform: uppercase; letter-spacing: 0.06em;
    }}
    table.summary td {{ padding: 7px 12px; border-bottom: 1px solid #252830; }}
    table.summary tr:hover td {{ background: #22263a; }}
    table.summary .strategy-row td {{ background: #1e2438; }}
    table.summary .strategy-row:hover td {{ background: #252c45; }}
    /* Heatmap */
    table.heatmap {{ border-collapse: collapse; min-width: 100%; white-space: nowrap; }}
    table.heatmap th {{
      padding: 7px 10px; background: #1e2030; color: #aaa;
      font-size: 11px; font-weight: 600; text-transform: uppercase;
      border-bottom: 2px solid #333; position: sticky; top: 0; z-index: 2;
    }}
    table.heatmap td {{
      padding: 6px 10px; text-align: center; font-size: 12px;
      border: 1px solid #2a2d3a;
    }}
    table.heatmap td:first-child {{ text-align: left; background: #1a1d27 !important;
      color: #ccc; font-size: 12px; position: sticky; left: 0; z-index: 1; }}
    table.heatmap .na {{ color: #555; background: #1a1d27 !important; }}
    .ytd {{
      background: #2196F3; color: #fff; font-size: 9px; padding: 1px 4px;
      border-radius: 3px; margin-left: 4px; vertical-align: middle;
    }}
    /* Chart containers */
    .chart-wrap {{ position: relative; }}
    canvas {{ max-height: 440px; }}
    /* Scrollable heatmap */
    .heatmap-scroll {{ overflow-x: auto; }}
  </style>
</head>
<body>

<h1>ETF &amp; Strategy Yearly Returns Dashboard</h1>
<p class="subtitle">
  ETFs: {", ".join(ETF_TICKERS)} &nbsp;|&nbsp; Strategy: {strat_label} &nbsp;|&nbsp;
  Generated: {datetime.date.today().strftime("%B %d, %Y")}
</p>

<!-- ── Section 1: Summary Stats ─────────────────────────────────────────── -->
<h2>Summary Statistics</h2>
<div class="card">
  <table class="summary">
    <thead>
      <tr>
        <th>Ticker / Strategy</th>
        <th>Inception</th>
        <th>CAGR</th>
        <th>Max DD</th>
        <th>Sharpe</th>
        <th>Best Year</th>
        <th>Worst Year</th>
      </tr>
    </thead>
    <tbody>
      {summary_rows}
    </tbody>
  </table>
</div>

<!-- ── Section 2: Grouped Bar Chart ─────────────────────────────────────── -->
<h2>Yearly Returns — Grouped Bar Chart</h2>
<div class="card chart-wrap">
  <canvas id="barChart"></canvas>
</div>

<!-- ── Section 3: Heatmap ────────────────────────────────────────────────── -->
<h2>Yearly Returns Heatmap</h2>
<div class="card heatmap-scroll">
  <table class="heatmap">
    <thead>
      <tr>
        <th>Year</th>
        {heatmap_header}
      </tr>
    </thead>
    <tbody>
      {heatmap_rows}
    </tbody>
  </table>
</div>

<!-- ── Section 4: Growth of $10,000 ─────────────────────────────────────── -->
<h2>Growth of $10,000 (Log Scale)</h2>
<div class="card chart-wrap">
  <canvas id="lineChart"></canvas>
</div>

<script>
// ── Shared data ──────────────────────────────────────────────────────────────
const YEARS  = {years_js};
const nullSafe = v => v === null || v === undefined ? null : v;

// ── Bar Chart ─────────────────────────────────────────────────────────────────
(function() {{
  const datasets = {bar_datasets_js};
  // replace null-ish with null for Chart.js
  datasets.forEach(ds => {{ ds.data = ds.data.map(nullSafe); }});

  new Chart(document.getElementById('barChart'), {{
    type: 'bar',
    data: {{ labels: YEARS.map(String), datasets }},
    options: {{
      responsive: true,
      plugins: {{
        legend: {{ position: 'top', labels: {{ color: '#ccc', font: {{ size: 11 }} }} }},
        tooltip: {{
          callbacks: {{
            label: ctx => {{
              const v = ctx.raw;
              if (v === null) return `${{ctx.dataset.label}}: N/A`;
              return `${{ctx.dataset.label}}: ${{v > 0 ? "+" : ""}}${{v.toFixed(1)}}%`;
            }}
          }}
        }}
      }},
      scales: {{
        x: {{
          ticks: {{ color: '#888', font: {{ size: 11 }} }},
          grid: {{ color: '#222' }},
        }},
        y: {{
          ticks: {{
            color: '#888', font: {{ size: 11 }},
            callback: v => v + '%'
          }},
          grid: {{ color: '#2a2d3a' }},
          afterBuildTicks: axis => {{
            // ensure -50, 0, +50, +100 are always shown
            const extras = [-50, 0, 50, 100];
            const existing = new Set(axis.ticks.map(t => t.value));
            extras.forEach(e => {{ if (!existing.has(e)) axis.ticks.push({{ value: e }}); }});
            axis.ticks.sort((a, b) => a.value - b.value);
          }},
        }}
      }}
    }}
  }});
}})();

// ── Line Chart (log scale) ────────────────────────────────────────────────────
(function() {{
  const datasets = {line_datasets_js};
  datasets.forEach(ds => {{ ds.data = ds.data.map(nullSafe); }});

  new Chart(document.getElementById('lineChart'), {{
    type: 'line',
    data: {{ labels: YEARS.map(String), datasets }},
    options: {{
      responsive: true,
      spanGaps: false,
      plugins: {{
        legend: {{ position: 'top', labels: {{ color: '#ccc', font: {{ size: 11 }} }} }},
        tooltip: {{
          callbacks: {{
            label: ctx => {{
              const v = ctx.raw;
              if (v === null) return null;
              return `${{ctx.dataset.label}}: $${{v.toLocaleString(undefined, {{maximumFractionDigits: 0}})}}`;
            }}
          }}
        }}
      }},
      scales: {{
        x: {{
          ticks: {{ color: '#888', font: {{ size: 11 }} }},
          grid: {{ color: '#222' }},
        }},
        y: {{
          type: 'logarithmic',
          ticks: {{
            color: '#888', font: {{ size: 11 }},
            callback: v => '$' + v.toLocaleString()
          }},
          grid: {{ color: '#2a2d3a' }},
        }}
      }}
    }}
  }});
}})();
</script>
</body>
</html>
"""
    return html


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    # 1. Download ETFs
    close_df = download_etfs(ETF_TICKERS, START_DATE)

    # 2. Compute yearly ETF returns
    etf_yr_rets = yearly_returns_from_prices(close_df)
    for t, d in etf_yr_rets.items():
        print(f"  {t}: {len(d)} years of data  ({min(d)} – {max(d)})" if d else f"  {t}: no data")

    # 3. Strategy returns
    print(f"\nReading strategy CSV from:\n  {BACKTEST_CSV}")
    strat_yr_ret = strategy_yearly_returns(BACKTEST_CSV)
    print(f"  Strategy: {len(strat_yr_ret)} years  ({min(strat_yr_ret)} – {max(strat_yr_ret)})")

    # 4. Summary stats
    stats = summary_stats(close_df, etf_yr_rets, strat_yr_ret, STRATEGY_LABEL)

    # 5. Growth series
    growth_data = growth_series(close_df, etf_yr_rets, strat_yr_ret, STRATEGY_LABEL)

    # 6. Build HTML
    print("\nBuilding HTML dashboard …")
    html = build_html(stats, etf_yr_rets, strat_yr_ret, STRATEGY_LABEL, growth_data)

    # 7. Write file
    os.makedirs(os.path.dirname(OUTPUT_HTML), exist_ok=True)
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n✅  Dashboard written to:\n    {OUTPUT_HTML}")


if __name__ == "__main__":
    main()
