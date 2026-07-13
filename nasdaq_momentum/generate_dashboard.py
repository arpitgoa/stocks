"""
Universal Dashboard Generator
==============================
Generates an interactive HTML dashboard from backtest CSV output.

Usage:
    python generate_dashboard.py --universe sp500
    python generate_dashboard.py --universe russell1000
    python generate_dashboard.py --universe nasdaq100

Reads: {universe}_backtest_wide.csv
Outputs: {universe}_momentum_dashboard.html
"""

import argparse
import pandas as pd
import json
from pathlib import Path

NORGATE_DIR = Path.home() / "Documents" / "workspace" / "historical-index-universe-data"
PRICES_DIR = NORGATE_DIR / "prices"
OUTPUT_DIR = Path.home() / "Documents" / "workspace" / "stocks" / "nasdaq_momentum"

UNIVERSE_LABELS = {
    "nasdaq100": "NASDAQ-100",
    "sp500": "S&P 500",
    "sp100": "S&P 100",
    "russell1000": "Russell 1000",
    "russell2000": "Russell 2000",
    "russell3000": "Russell 3000",
    "russell_midcap": "Russell Mid Cap",
    "russell_top200": "Russell Top 200",
    "djia": "Dow Jones Industrial Average",
    "sp_midcap400": "S&P MidCap 400",
    "sp_smallcap600": "S&P SmallCap 600",
    "sp1500": "S&P 1500",
    "nasdaq_q50": "NASDAQ Q-50",
    "nasdaq_biotech": "NASDAQ Biotech",
}


def load_bench_prices(needed_tickers):
    """Load price data only for tickers needed for bench returns."""
    print(f"  Loading prices for {len(needed_tickers)} bench tickers...")
    file_map = {f.stem.split("__")[0]: f for f in PRICES_DIR.glob("*.csv")}
    all_close = {}
    for ticker in needed_tickers:
        if ticker in file_map:
            df = pd.read_csv(file_map[ticker], usecols=["Date", "Close"], index_col="Date", parse_dates=True)
            all_close[ticker] = df["Close"]
    prices = pd.DataFrame(all_close).sort_index()
    print(f"  Loaded {prices.shape[1]} tickers")
    return prices


def generate_dashboard(universe_name):
    """Generate HTML dashboard for a universe's backtest results."""
    label = UNIVERSE_LABELS.get(universe_name, universe_name.upper())
    dashboard_dir = OUTPUT_DIR / "dashboards" / universe_name
    csv_file = dashboard_dir / "backtest_wide.csv"

    if not csv_file.exists():
        print(f"Error: {csv_file} not found. Run backtest first:")
        print(f"  python run_backtest.py --universe {universe_name}")
        return

    print(f"Generating dashboard for {label}...")
    df = pd.read_csv(csv_file)

    # Determine which tickers we need prices for (only those in Top10 that aren't held)
    needed_tickers = set()
    for top10_str in df["Top10"].dropna():
        for t in str(top10_str).split(", "):
            t = t.strip()
            if t and not t.startswith("GOLD"):
                needed_tickers.add(t)

    # Load prices only for needed tickers
    prices = load_bench_prices(needed_tickers)

    # Build data for HTML
    data = []
    for _, row in df.iterrows():
        # Get held tickers and their weights
        holdings = {}
        for col in df.columns:
            if col.endswith("_Pct") and row[col] != "" and pd.notna(row[col]):
                ticker = col.replace("_Pct", "")
                if ticker not in ("Portfolio_Return", "Benchmark_Return", "QQQ_Return", "Leveraged_Return"):
                    holdings[ticker] = float(row[col])

        # Get ticker returns
        returns = {}
        for col in df.columns:
            if col.endswith("_Ret") and row[col] != "" and pd.notna(row[col]):
                ticker = col.replace("_Ret", "")
                returns[ticker] = float(row[col])

        # Compute bench returns for non-held top 10
        bench_returns = {}
        top10_str = row.get("Top10", "")
        if top10_str and pd.notna(top10_str):
            top10_list = [t.strip() for t in str(top10_str).split(",")]
            start_date = row["Start_Date"]
            end_date = row["End_Date"]
            for ticker in top10_list:
                if ticker not in holdings and ticker in prices.columns:
                    period = prices.loc[start_date:end_date, ticker].dropna()
                    if len(period) >= 2:
                        ret = round(((period.iloc[-1] / period.iloc[0]) - 1) * 100, 2)
                        bench_returns[ticker] = ret

        data.append({
            "start": row["Start_Date"],
            "end": row["End_Date"],
            "portStart": float(row["Portfolio_Start"]),
            "portEnd": float(row["Portfolio_End"]),
            "portRet": float(row["Portfolio_Return_Pct"]),
            "qqqRet": float(row["Benchmark_Return_Pct"]) if row["Benchmark_Return_Pct"] != "" and pd.notna(row["Benchmark_Return_Pct"]) else None,
            "holdings": holdings,
            "returns": returns,
            "benchReturns": bench_returns,
            "top7": row.get("Top10", ""),
            "changes": row.get("Changes", ""),
        })

    # Determine start date for the input
    start_month = data[0]["start"][:7]

    html_content = _build_html(data, label, start_month)

    output_file = dashboard_dir / "dashboard.html"
    with open(output_file, "w") as f:
        f.write(html_content)

    print(f"Generated: {output_file}")
    print(f"  Data points: {len(data)} months")


def _build_html(data, label, start_month):
    """Build the full HTML dashboard string."""
    data_json = json.dumps(data)

    return f"""<!DOCTYPE html>
<html><head>
<title>{label} Momentum Strategy Backtest</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 20px; background: #f8f9fa; }}
h1 {{ color: #333; margin-bottom: 5px; }}
h3 {{ color: #666; margin-top: 0; font-weight: normal; }}
.controls {{ background: white; padding: 15px; border-radius: 8px; margin-bottom: 15px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); display: flex; align-items: center; gap: 15px; flex-wrap: wrap; }}
.controls label {{ font-size: 13px; font-weight: bold; }}
.controls input {{ padding: 5px 8px; border: 1px solid #ddd; border-radius: 4px; font-size: 13px; }}
.summary {{ background: white; padding: 15px; border-radius: 8px; margin-bottom: 15px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
.summary-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; }}
.summary-card {{ padding: 10px; border-radius: 6px; background: #f8f9fa; }}
.summary-card .label {{ font-size: 10px; color: #666; text-transform: uppercase; }}
.summary-card .value {{ font-size: 18px; font-weight: bold; margin-top: 3px; }}
.s1 {{ border-left: 3px solid #1f77b4; }}
.s2 {{ border-left: 3px solid #ff7f0e; }}
.s3 {{ border-left: 3px solid #2ca02c; }}
#chartContainer {{ background: white; border-radius: 8px; padding: 15px; margin-bottom: 15px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); height: 350px; }}
#yearlyChartContainer {{ background: white; border-radius: 8px; padding: 15px; margin-bottom: 15px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); height: 350px; }}
table {{ border-collapse: collapse; width: 100%; background: white; font-size: 11px; }}
th {{ background: #343a40; color: white; padding: 7px 4px; text-align: right; position: sticky; top: 0; }}
th:first-child, th:nth-child(2) {{ text-align: left; }}
td {{ padding: 5px 4px; border-bottom: 1px solid #eee; text-align: right; white-space: nowrap; }}
td:first-child, td:nth-child(2) {{ text-align: left; }}
tr:hover {{ background: #e9ecef !important; }}
.pos {{ color: #28a745; }}
.neg {{ color: #dc3545; }}
.tag {{ display: inline-block; padding: 1px 4px; border-radius: 3px; font-size: 9px; margin: 1px; }}
.tag-held {{ background: #d4edda; color: #155724; }}
#tableContainer {{ max-height: 600px; overflow-y: auto; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
</style>
</head><body>
<h1>{label} Momentum Top 3 Strategy</h1>
<h3>Monthly rebalance · Buffer 3/7 · Equal weight · Gold rotation (NDX/XAUUSD ≥ 7.0)</h3>

<div class="controls">
<div><label>Initial ($):</label> <input type="number" id="initialAmt" value="100000" min="0" step="10000" style="width:100px;"></div>
<div><label>Monthly DCA ($):</label> <input type="number" id="monthlyAmt" value="1000" min="0" step="100" style="width:80px;"></div>
<div><label>Start:</label> <input type="month" id="startDate" value="{start_month}"></div>
<div><label>End:</label> <input type="month" id="endDate" value="2026-07"></div>
<div><button onclick="recalculate()" style="padding:7px 16px;background:#343a40;color:white;border:none;border-radius:4px;cursor:pointer;">Apply</button></div>
</div>

<div class="summary" id="summary"></div>
<div id="chartContainer" style="position:relative;"><canvas id="chart"></canvas></div>
<div id="yearlyChartContainer"><canvas id="yearlyChart"></canvas></div>
<div id="tableContainer"></div>

<script>
const RAW_DATA = {data_json};
let chart = null;

function recalculate() {{
    const initial = parseFloat(document.getElementById('initialAmt').value) || 100000;
    const monthly = parseFloat(document.getElementById('monthlyAmt').value) || 0;
    const startFilter = document.getElementById('startDate').value;
    const endFilter = document.getElementById('endDate').value;

    const filtered = RAW_DATA.filter(d => {{
        const m = d.start.substring(0,7);
        return m >= startFilter && m <= endFilter;
    }});
    if (filtered.length === 0) return;

    let portValue = initial, benchValue = initial, totalInvested = initial;
    const results = [];

    for (const d of filtered) {{
        portValue *= (1 + d.portRet / 100);
        if (d.qqqRet !== null) benchValue *= (1 + d.qqqRet / 100);
        portValue += monthly;
        benchValue += monthly;
        totalInvested += monthly;
        results.push({{ ...d, cumPort: portValue, cumBench: benchValue, totalInvested }});
    }}

    const years = filtered.length / 12;
    const portCAGR = Math.pow(portValue / initial, 1/years) - 1;
    const benchCAGR = Math.pow(benchValue / initial, 1/years) - 1;
    let peak = initial, maxDD = 0;
    for (const r of results) {{
        if (r.cumPort > peak) peak = r.cumPort;
        const dd = (peak - r.cumPort) / peak;
        if (dd > maxDD) maxDD = dd;
    }}

    // Streaks
    let portWinStreak=0, portLoseStreak=0, cw=0, cl=0;
    for (const r of results) {{
        if (r.portRet > 0) {{ cw++; cl=0; if(cw>portWinStreak) portWinStreak=cw; }}
        else {{ cl++; cw=0; if(cl>portLoseStreak) portLoseStreak=cl; }}
    }}
    const portWinRate = results.filter(r => r.portRet > 0).length;

    document.getElementById('summary').innerHTML = `
    <div class="summary-grid">
        <div class="summary-card s3">
            <div class="label">Period</div>
            <div class="value">${{filtered[0].start.substring(0,7)}} — ${{filtered[filtered.length-1].end.substring(0,7)}}</div>
            <div style="font-size:12px;color:#555;">${{filtered.length}} months · Invested $${{totalInvested.toLocaleString(undefined,{{maximumFractionDigits:0}})}}</div>
        </div>
        <div class="summary-card s1">
            <div class="label">Momentum Strategy</div>
            <div class="value">$${{portValue.toLocaleString(undefined,{{maximumFractionDigits:0}})}}</div>
            <div style="font-size:12px;color:#555;">${{(portValue/totalInvested).toFixed(1)}}x · CAGR ${{(portCAGR*100).toFixed(1)}}% · <span style="color:#dc3545;">Max DD -${{(maxDD*100).toFixed(1)}}%</span></div>
            <div style="font-size:11px;">Win: ${{portWinRate}}/${{filtered.length}} (${{(portWinRate/filtered.length*100).toFixed(0)}}%) · <span style="color:#28a745;">Win streak: ${{portWinStreak}}mo</span> · <span style="color:#dc3545;">Lose streak: ${{portLoseStreak}}mo</span></div>
        </div>
        <div class="summary-card s2">
            <div class="label">Benchmark (Buy & Hold)</div>
            <div class="value">$${{benchValue.toLocaleString(undefined,{{maximumFractionDigits:0}})}}</div>
            <div style="font-size:12px;color:#555;">${{(benchValue/totalInvested).toFixed(1)}}x · CAGR ${{(benchCAGR*100).toFixed(1)}}%</div>
        </div>
    </div>`;

    // Chart
    if (chart) chart.destroy();
    chart = new Chart(document.getElementById('chart'), {{
        type: 'line',
        data: {{
            labels: results.map(r => r.start.substring(0,7)),
            datasets: [
                {{ label: 'Momentum', data: results.map(r => r.cumPort), borderColor: '#1f77b4', borderWidth: 1.5, pointRadius: 0, fill: false }},
                {{ label: 'Benchmark', data: results.map(r => r.cumBench), borderColor: '#ff7f0e', borderWidth: 1.5, pointRadius: 0, fill: false }},
                {{ label: 'Invested', data: results.map(r => r.totalInvested), borderColor: '#999', borderWidth: 1, borderDash: [4,4], pointRadius: 0, fill: false }},
            ]
        }},
        options: {{
            responsive: true, maintainAspectRatio: false,
            interaction: {{ mode: 'index', intersect: false }},
            scales: {{ y: {{ type: 'logarithmic' }}, x: {{ ticks: {{ maxTicksLimit: 20 }} }} }},
            plugins: {{ legend: {{ position: 'top' }} }}
        }}
    }});

    // Yearly bar chart
    const yearly = {{}};
    for (const r of results) {{
        const y = r.start.substring(0,4);
        if (!yearly[y]) yearly[y] = {{port:1, bench:1}};
        yearly[y].port *= (1 + r.portRet/100);
        if (r.qqqRet !== null) yearly[y].bench *= (1 + r.qqqRet/100);
    }}
    const yLabels = Object.keys(yearly).sort();
    const yPort = yLabels.map(y => (yearly[y].port-1)*100);
    const yBench = yLabels.map(y => (yearly[y].bench-1)*100);

    if (window.yChart) window.yChart.destroy();
    window.yChart = new Chart(document.getElementById('yearlyChart'), {{
        type: 'bar',
        data: {{
            labels: yLabels,
            datasets: [
                {{ label: 'Momentum', data: yPort, backgroundColor: yPort.map(v => v>=0 ? '#1f77b4' : '#aec7e8') }},
                {{ label: 'Benchmark', data: yBench, backgroundColor: yBench.map(v => v>=0 ? '#ff7f0e' : '#ffbb78') }},
            ]
        }},
        options: {{
            responsive: true, maintainAspectRatio: false,
            plugins: {{ legend: {{ position: 'top' }}, title: {{ display: true, text: 'Annual Returns (%)' }} }},
            scales: {{ y: {{ ticks: {{ callback: v => v+'%' }} }} }}
        }}
    }});

    // Table
    let html = '<table><thead><tr><th>Period</th><th>Port Ret</th><th>Bench Ret</th><th>Port Value</th><th>Bench Value</th><th>Chg</th><th>Swaps</th><th>Holdings</th><th>Bench (4-10)</th></tr></thead><tbody>';
    let prev = new Set();
    for (const r of results) {{
        const curr = new Set(Object.keys(r.holdings));
        const changes = Math.max([...curr].filter(t=>!prev.has(t)).length, [...prev].filter(t=>!curr.has(t)).length);
        prev = curr;

        let holdHtml = '';
        for (const [t, w] of Object.entries(r.holdings).sort((a,b)=>b[1]-a[1])) {{
            const ret = r.returns[t];
            const rs = ret !== undefined ? ` ${{ret>0?'+':''}}${{ret.toFixed(1)}}%` : '';
            const rc = ret > 0 ? 'pos' : (ret < 0 ? 'neg' : '');
            holdHtml += `<span class="tag tag-held">${{t}}<span class="${{rc}}">${{rs}}</span></span> `;
        }}

        const bench = r.benchReturns || {{}};
        const benchHtml = Object.entries(bench).map(([t,ret]) => {{
            const rc = ret>0?'pos':(ret<0?'neg':'');
            return `<span class="tag" style="background:#e2e3e5;color:#383d41;">${{t}} <span class="${{rc}}">${{(ret>0?'+':'')+ret.toFixed(1)}}%</span></span>`;
        }}).join(' ') || '-';

        const pc = r.portRet>=0?'pos':'neg';
        const bc = (r.qqqRet||0)>=0?'pos':'neg';
        html += `<tr>
            <td>${{r.end.substring(0,7)}}</td>
            <td class="${{pc}}">${{r.portRet>0?'+':''}}${{r.portRet.toFixed(1)}}%</td>
            <td class="${{bc}}">${{r.qqqRet!==null?(r.qqqRet>0?'+':'')+r.qqqRet.toFixed(1)+'%':'-'}}</td>
            <td>$${{r.cumPort.toLocaleString(undefined,{{maximumFractionDigits:0}})}}</td>
            <td>$${{r.cumBench.toLocaleString(undefined,{{maximumFractionDigits:0}})}}</td>
            <td>${{changes>0?changes:'-'}}</td>
            <td style="font-size:10px;">${{r.changes||'-'}}</td>
            <td style="text-align:left">${{holdHtml}}</td>
            <td style="text-align:left">${{benchHtml}}</td>
        </tr>`;
    }}
    html += '</tbody></table>';
    document.getElementById('tableContainer').innerHTML = html;
}}

recalculate();
</script>
</body></html>"""


def main():
    parser = argparse.ArgumentParser(description="Generate momentum dashboard")
    parser.add_argument("--universe", type=str, required=False, help="Universe name")
    parser.add_argument("--all", action="store_true", help="Generate dashboards for all universes with backtest data")
    args = parser.parse_args()

    if args.all:
        from universe_config import UNIVERSE_CONFIGS
        dashboard_base = OUTPUT_DIR / "dashboards"
        for name in UNIVERSE_CONFIGS:
            csv_path = dashboard_base / name / "backtest_wide.csv"
            if csv_path.exists():
                generate_dashboard(name)
            else:
                print(f"  Skipping {name} (no backtest data)")
    elif args.universe:
        generate_dashboard(args.universe)
    else:
        print("Error: --universe or --all required.")


if __name__ == "__main__":
    main()
