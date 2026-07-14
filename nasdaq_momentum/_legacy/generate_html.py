"""
Generate interactive HTML dashboard for the momentum backtest results.
Reads the backtest CSV and creates a self-contained HTML file.
"""

import pandas as pd
import json

# Load backtest results
df = pd.read_csv("backtest_wide_holdings.csv")

# Load price data to compute returns for non-held top 7 stocks
from load_norgate_data import load_prices as _load_norgate_prices
prices = _load_norgate_prices()

# Build data for HTML
data = []
for _, row in df.iterrows():
    # Get held tickers and their weights
    holdings = {}
    for col in df.columns:
        if col.endswith("_Pct") and row[col] != "" and pd.notna(row[col]):
            ticker = col.replace("_Pct", "")
            holdings[ticker] = float(row[col])
    
    # Get ticker returns
    returns = {}
    lev_returns = {}
    for col in df.columns:
        if col.endswith("_Ret") and not col.endswith("_LevRet") and row[col] != "" and pd.notna(row[col]):
            ticker = col.replace("_Ret", "")
            returns[ticker] = float(row[col])
        if col.endswith("_LevRet") and row[col] != "" and pd.notna(row[col]):
            ticker = col.replace("_LevRet", "")
            lev_returns[ticker] = float(row[col])
    
    # Compute returns for non-held top ranked stocks (bench stocks at ranks 4-10)
    bench_returns = {}
    top7_str = row.get("Top7", "")
    if top7_str and pd.notna(top7_str):
        top7_list = [t.strip() for t in str(top7_str).split(",")]
        start_date = row["Start_Date"]
        end_date = row["End_Date"]
        # Get top 10 from the list (top7 only has 7, so we'll use what's available)
        for ticker in top7_list:
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
        "qqqRet": float(row["QQQ_Return_Pct"]) if row["QQQ_Return_Pct"] != "" and pd.notna(row["QQQ_Return_Pct"]) else None,
        "levRet": float(row["Leveraged_Return_Pct"]) if "Leveraged_Return_Pct" in row and row["Leveraged_Return_Pct"] != "" and pd.notna(row.get("Leveraged_Return_Pct")) else None,
        "holdings": holdings,
        "returns": returns,
        "levReturns": lev_returns,
        "benchReturns": bench_returns,
        "top7": row.get("Top7", ""),
        "changes": row.get("Changes", ""),
    })

# Get all tickers ever held
all_tickers = sorted(set(
    ticker
    for d in data
    for ticker in d["holdings"].keys()
))

html = f"""<!DOCTYPE html>
<html><head>
<title>NASDAQ-100 Momentum Strategy Backtest</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 20px; background: #f8f9fa; }}
h1 {{ color: #333; margin-bottom: 5px; }}
h3 {{ color: #666; margin-top: 0; font-weight: normal; }}
.controls {{ background: white; padding: 15px; border-radius: 8px; margin-bottom: 15px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); display: flex; align-items: center; gap: 15px; flex-wrap: wrap; }}
.controls label {{ font-size: 13px; font-weight: bold; }}
.controls input, .controls select {{ padding: 5px 8px; border: 1px solid #ddd; border-radius: 4px; font-size: 13px; }}
.summary {{ background: white; padding: 15px; border-radius: 8px; margin-bottom: 15px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
.summary-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }}
.summary-card {{ padding: 10px; border-radius: 6px; background: #f8f9fa; }}
.summary-card .label {{ font-size: 10px; color: #666; text-transform: uppercase; }}
.summary-card .value {{ font-size: 18px; font-weight: bold; margin-top: 3px; }}
.s1 {{ border-left: 3px solid #1f77b4; }}
.s2 {{ border-left: 3px solid #ff7f0e; }}
.s3 {{ border-left: 3px solid #2ca02c; }}
.s4 {{ border-left: 3px solid #d62728; }}
#chartContainer {{ background: white; border-radius: 8px; padding: 15px; margin-bottom: 15px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); height: 350px; }}
table {{ border-collapse: collapse; width: 100%; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1); font-size: 11px; }}
th {{ background: #343a40; color: white; padding: 7px 4px; text-align: right; position: sticky; top: 0; z-index: 10; white-space: nowrap; }}
th:first-child, th:nth-child(2) {{ text-align: left; }}
td {{ padding: 5px 4px; border-bottom: 1px solid #eee; text-align: right; white-space: nowrap; }}
td:first-child, td:nth-child(2) {{ text-align: left; }}
tr:hover {{ background: #e9ecef !important; }}
.pos {{ color: #28a745; }}
.neg {{ color: #dc3545; }}
.tag {{ display: inline-block; padding: 1px 4px; border-radius: 3px; font-size: 9px; margin: 1px; }}
.tag-held {{ background: #d4edda; color: #155724; }}
.tag-new {{ background: #cce5ff; color: #004085; }}
.tag-exit {{ background: #f8d7da; color: #721c24; }}
#tableContainer {{ max-height: 600px; overflow-y: auto; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
#yearlyChartContainer {{ background: white; border-radius: 8px; padding: 15px; margin-bottom: 15px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); height: 350px; }}
#stockStats {{ background: white; border-radius: 8px; padding: 15px; margin-bottom: 15px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
#stockStats h4 {{ margin: 0 0 10px 0; color: #333; }}
.stats-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 15px; }}
.stats-table {{ width: 100%; border-collapse: collapse; font-size: 11px; }}
.stats-table th {{ background: #f8f9fa; padding: 6px 8px; text-align: left; border-bottom: 2px solid #dee2e6; color: #333; cursor: pointer; user-select: none; }}
.stats-table th:hover {{ background: #e9ecef; }}
.stats-table th::after {{ content: ' ⇅'; font-size: 9px; color: #aaa; }}
.stats-table td {{ padding: 5px 8px; border-bottom: 1px solid #eee; color: #333; }}
</style>
</head><body>
<div id="infoModal" onclick="if(event.target===this)this.style.display='none'" style="display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.5);z-index:99999;justify-content:center;align-items:center;">
<div style="background:white;border-radius:12px;padding:30px;max-width:700px;max-height:80vh;overflow-y:auto;margin:20px;box-shadow:0 4px 20px rgba(0,0,0,0.3);">
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;">
<h2 style="margin:0;">Strategy Methodology</h2>
<button onclick="document.getElementById('infoModal').style.display='none'" style="background:none;border:none;font-size:24px;cursor:pointer;">✕</button>
</div>
<div style="font-size:13px;line-height:1.7;color:#333;">
<h3>1. Universe</h3>
<p>NASDAQ-100 constituents (point-in-time, verified yearly membership).</p>

<h3>2. Momentum Score Calculation</h3>
<p>For each stock, calculate the <strong>Normalized Momentum Score</strong>:</p>
<ol>
<li><strong>12-month return</strong> (skip last 5 trading days): Price(end) / Price(252 days ago) - 1</li>
<li><strong>6-month return</strong> (skip last 5 trading days): Price(end) / Price(126 days ago) - 1</li>
<li><strong>Annualized volatility (σ)</strong>: Std dev of daily log returns × √252</li>
<li><strong>Momentum Ratios</strong>: MR_12 = 12M return / σ, MR_6 = 6M return / σ</li>
<li><strong>Z-Scores</strong>: Z_12 = (MR_12 of stock - mean of all MR_12) / std dev of all MR_12. Same for Z_6. Measures how many std devs above/below the universe average.</li>
<li><strong>Weighted Z</strong>: 50% × Z_12 + 50% × Z_6</li>
<li><strong>Score</strong>: If Z ≥ 0 → (1 + Z), else → (1 - Z)⁻¹</li>
</ol>

<h3>3. Stock Selection (Buffer Logic)</h3>
<ul>
<li>Rank all stocks by Normalized Momentum Score</li>
<li>A <strong>new stock enters</strong> only if ranked ≤ 3</li>
<li>An <strong>existing stock stays</strong> unless it drops below rank 7</li>
<li>Target portfolio: <strong>3 stocks</strong>, equal weight (~33% each)</li>
</ul>

<h3>4. QQQ/GLD Rotation</h3>
<ul>
<li>Before stock selection, check QQQ price / GLD price</li>
<li>If <strong>QQQ/GLD ≥ 2.0</strong>: Skip stocks, hold 100% GLD for the month</li>
<li>If QQQ/GLD &lt; 2.0: Normal momentum stock selection</li>
</ul>

<h3>5. Rebalance Schedule</h3>
<ul>
<li><strong>Membership check</strong>: Monthly (last trading day)</li>
<li><strong>Weight reset</strong>: Every 6 months (June & December)</li>
<li>Between resets: weights drift with price, only entry/exit trades happen</li>
</ul>

<h3>6. Leveraged Comparison</h3>
<ul>
<li>Same stock selection as above</li>
<li>If a 2x leveraged single-stock ETF exists (e.g., NVDL for NVDA), use it for returns</li>
<li>If no leveraged ETF available, use the regular stock</li>
</ul>

<h3>7. Parameters</h3>
<table style="border-collapse:collapse;width:100%;font-size:12px;">
<tr><td style="padding:4px 8px;border-bottom:1px solid #eee;"><strong>Stocks held</strong></td><td style="padding:4px 8px;border-bottom:1px solid #eee;">3</td></tr>
<tr><td style="padding:4px 8px;border-bottom:1px solid #eee;"><strong>Entry rank</strong></td><td style="padding:4px 8px;border-bottom:1px solid #eee;">≤ 3</td></tr>
<tr><td style="padding:4px 8px;border-bottom:1px solid #eee;"><strong>Exit rank</strong></td><td style="padding:4px 8px;border-bottom:1px solid #eee;">> 7</td></tr>
<tr><td style="padding:4px 8px;border-bottom:1px solid #eee;"><strong>Lookback</strong></td><td style="padding:4px 8px;border-bottom:1px solid #eee;">12M + 6M (50/50 blend)</td></tr>
<tr><td style="padding:4px 8px;border-bottom:1px solid #eee;"><strong>Skip period</strong></td><td style="padding:4px 8px;border-bottom:1px solid #eee;">Last 5 trading days</td></tr>
<tr><td style="padding:4px 8px;border-bottom:1px solid #eee;"><strong>Volatility</strong></td><td style="padding:4px 8px;border-bottom:1px solid #eee;">Annualized std dev of 252-day log returns</td></tr>
<tr><td style="padding:4px 8px;border-bottom:1px solid #eee;"><strong>GLD trigger</strong></td><td style="padding:4px 8px;border-bottom:1px solid #eee;">QQQ/GLD ≥ 2.0</td></tr>
<tr><td style="padding:4px 8px;border-bottom:1px solid #eee;"><strong>Rebalance</strong></td><td style="padding:4px 8px;border-bottom:1px solid #eee;">Monthly (membership) + 6-monthly (weights)</td></tr>
</table>
</div>
</div>
</div>
<h1>NASDAQ-100 Momentum Top 3 Strategy <button onclick="document.getElementById('infoModal').style.display='flex'" style="background:#6c757d;color:white;border:none;border-radius:50%;width:24px;height:24px;font-size:13px;cursor:pointer;vertical-align:middle;">i</button></h1>
<h3>Monthly membership (3/7 buffer) · Equal weight · 6-mo weight reset · 5-day skip · GLD when QQQ/GLD ≥ 2.0</h3>

<div class="controls">
<div><label>Initial ($):</label> <input type="number" id="initialAmt" value="100000" min="0" step="10000" style="width:100px;"></div>
<div><label>Monthly DCA ($):</label> <input type="number" id="monthlyAmt" value="1000" min="0" step="100" style="width:80px;"></div>
<div><label>Start:</label> <input type="month" id="startDate" value="1995-01"></div>
<div><label>End:</label> <input type="month" id="endDate" value="2026-07"></div>
<div><button onclick="recalculate()" style="padding:7px 16px;background:#343a40;color:white;border:none;border-radius:4px;cursor:pointer;">Apply</button></div>
</div>

<div class="summary" id="summary"></div>
<div id="chartContainer" style="position:relative;"><canvas id="chart"></canvas><button id="scaleToggle" onclick="toggleScale()" style="position:absolute;top:10px;right:10px;padding:4px 10px;font-size:11px;background:#f0f0f0;border:1px solid #ccc;border-radius:4px;cursor:pointer;">Linear</button></div>
<div id="yearlyChartContainer"><canvas id="yearlyChart"></canvas></div>
<div id="stockStats"></div>
<div id="tableContainer"></div>

<script>
const RAW_DATA = {json.dumps(data)};

let chart = null;

function recalculate() {{
    const initial = parseFloat(document.getElementById('initialAmt').value) || 100000;
    const monthly = parseFloat(document.getElementById('monthlyAmt').value) || 0;
    const startFilter = document.getElementById('startDate').value;
    const endFilter = document.getElementById('endDate').value;
    
    // Filter data by date range
    const filtered = RAW_DATA.filter(d => {{
        const m = d.start.substring(0,7);
        return m >= startFilter && m <= endFilter;
    }});
    
    if (filtered.length === 0) return;
    
    // Recalculate with DCA
    let portValue = initial;
    let qqqValue = initial;
    let levValue = initial;
    let totalInvested = initial;
    const results = [];
    
    for (let i = 0; i < filtered.length; i++) {{
        const d = filtered[i];
        const portStart = portValue;
        const qqqStart = qqqValue;
        
        // Apply returns
        portValue *= (1 + d.portRet / 100);
        if (d.qqqRet !== null) qqqValue *= (1 + d.qqqRet / 100);
        if (d.levRet !== null) levValue *= (1 + d.levRet / 100); else levValue *= (1 + d.portRet / 100);
        
        // Add DCA
        portValue += monthly;
        qqqValue += monthly;
        levValue += monthly;
        totalInvested += monthly;
        
        results.push({{
            ...d,
            cumPort: portValue,
            cumQQQ: qqqValue,
            cumLev: levValue,
            totalInvested: totalInvested,
        }});
    }}
    
    // Summary
    const years = filtered.length / 12;
    const portMultiple = portValue / totalInvested;
    const qqqMultiple = qqqValue / totalInvested;
    const portProfit = portValue - totalInvested;
    const qqqProfit = qqqValue - totalInvested;
    
    // Max drawdown
    let peak = initial, maxDD = 0;
    for (const r of results) {{
        if (r.cumPort > peak) peak = r.cumPort;
        const dd = (peak - r.cumPort) / peak;
        if (dd > maxDD) maxDD = dd;
    }}
    
    // XIRR approximation (simple geometric)
    const portCAGR = Math.pow(portValue / initial, 1/years) - 1;
    const qqqCAGR = Math.pow(qqqValue / initial, 1/years) - 1;
    const levCAGR = Math.pow(levValue / initial, 1/years) - 1;
    const levMultiple = levValue / totalInvested;
    
    const startLabel = filtered[0].start.substring(0,7);
    const endLabel = filtered[filtered.length-1].end.substring(0,7);
    const numMonths = filtered.length;
    
    // Max drawdown for QQQ
    let qqqPeak = initial, qqqMaxDD = 0, qqqVal = initial;
    for (const r of results) {{
        if (r.qqqRet !== null) qqqVal *= (1 + r.qqqRet/100);
        qqqVal += monthly;
        if (qqqVal > qqqPeak) qqqPeak = qqqVal;
        const dd = (qqqPeak - qqqVal) / qqqPeak;
        if (dd > qqqMaxDD) qqqMaxDD = dd;
    }}
    
    // Best/worst months
    let bestPort = {{ret: -Infinity, period: ''}}, worstPort = {{ret: Infinity, period: ''}};
    let bestQQQ = {{ret: -Infinity, period: ''}}, worstQQQ = {{ret: Infinity, period: ''}};
    for (const r of results) {{
        const period = r.start.substring(0,7);
        if (r.portRet > bestPort.ret) bestPort = {{ret: r.portRet, period}};
        if (r.portRet < worstPort.ret) worstPort = {{ret: r.portRet, period}};
        if (r.qqqRet !== null) {{
            if (r.qqqRet > bestQQQ.ret) bestQQQ = {{ret: r.qqqRet, period}};
            if (r.qqqRet < worstQQQ.ret) worstQQQ = {{ret: r.qqqRet, period}};
        }}
    }}
    
    // Win/Lose streaks
    let portWinStreak = 0, portLoseStreak = 0, portCurrWin = 0, portCurrLose = 0;
    let qqqWinStreak = 0, qqqLoseStreak = 0, qqqCurrWin = 0, qqqCurrLose = 0;
    for (const r of results) {{
        if (r.portRet > 0) {{ portCurrWin++; portCurrLose = 0; if (portCurrWin > portWinStreak) portWinStreak = portCurrWin; }}
        else {{ portCurrLose++; portCurrWin = 0; if (portCurrLose > portLoseStreak) portLoseStreak = portCurrLose; }}
        if (r.qqqRet !== null) {{
            if (r.qqqRet > 0) {{ qqqCurrWin++; qqqCurrLose = 0; if (qqqCurrWin > qqqWinStreak) qqqWinStreak = qqqCurrWin; }}
            else {{ qqqCurrLose++; qqqCurrWin = 0; if (qqqCurrLose > qqqLoseStreak) qqqLoseStreak = qqqCurrLose; }}
        }}
    }}
    const portWinRate = results.filter(r => r.portRet > 0).length;
    const qqqWinRate = results.filter(r => r.qqqRet !== null && r.qqqRet > 0).length;
    
    // Next month card — show current holdings and top 7
    const lastResult = results[results.length - 1];
    let nextMonthHtml = '';
    if (lastResult) {{
        const currentHoldings = Object.keys(lastResult.holdings).filter(t => !t.includes('Return') && !t.includes('QQQ'));
        const top7 = lastResult.top7 ? lastResult.top7.split(', ') : [];
        const levMap2 = {{"AAPL":"AAPU","AMD":"AMUU","AMZN":"AMZU","ARM":"ARMU","AVGO":"AVGU","COIN":"CONL","CRWD":"CRWU","GOOG":"GGLL","GOOGL":"GGLL","HOOD":"HODU","META":"METU","MSFT":"MSFU","MSTR":"MSTU","MU":"MUU","NFLX":"NFLU","NVDA":"NVDL","ORCL":"ORCU","PLTR":"PLTU","QCOM":"QCMU","SMCI":"SMCX","TSLA":"TSLL","TTD":"TTDU"}};
        nextMonthHtml = `
        <div class="summary-card s1" style="border-left-color:#333;">
            <div class="label">📊 Next Month Buy</div>
            <div class="value">${{currentHoldings.join(', ')}}</div>
            <div style="font-size:12px;color:#555;margin-top:4px;">Lev: ${{currentHoldings.map(t => levMap2[t] || t).join(', ')}}</div>
            <div style="font-size:11px;margin-top:3px;">Top 7: ${{top7.map((t,i) => i < 3 ? '<strong>'+t+'</strong>' : t).join(', ')}}</div>
        </div>`;
    }}
    document.getElementById('summary').parentElement; // nextMonthCard is now inside summary
    
    // Max drawdown for leveraged
    let levPeak = initial, levMaxDD = 0, levVal2 = initial;
    let bestLev = {{ret: -Infinity, period: ''}}, worstLev = {{ret: Infinity, period: ''}};
    for (const r of results) {{
        const lr = r.levRet !== null ? r.levRet : r.portRet;
        levVal2 *= (1 + lr/100);
        levVal2 += monthly;
        if (levVal2 > levPeak) levPeak = levVal2;
        const dd = (levPeak - levVal2) / levPeak;
        if (dd > levMaxDD) levMaxDD = dd;
        const period = r.start.substring(0,7);
        if (lr > bestLev.ret) bestLev = {{ret: lr, period}};
        if (lr < worstLev.ret) worstLev = {{ret: lr, period}};
    }}
    
    document.getElementById('summary').innerHTML = `
    <div class="summary-grid">
        <div class="summary-card s3">
            <div class="label">Period</div>
            <div class="value">` + startLabel + ` — ` + endLabel + `</div>
            <div style="font-size:12px;color:#555;margin-top:4px;">` + numMonths + ` months · Invested $` + totalInvested.toLocaleString(undefined,{{maximumFractionDigits:0}}) + `</div>
        </div>` + nextMonthHtml + `
        <div class="summary-card s1">
            <div class="label">Momentum Strategy</div>
            <div class="value">$` + portValue.toLocaleString(undefined,{{maximumFractionDigits:0}}) + `</div>
            <div style="font-size:12px;color:#555;margin-top:4px;">` + portMultiple.toFixed(1) + `x · CAGR ` + (portCAGR*100).toFixed(1) + `% · <span style="color:#dc3545;">Max DD -` + (maxDD*100).toFixed(1) + `%</span></div>
            <div style="font-size:11px;margin-top:3px;"><span style="color:#28a745;">Best: +` + bestPort.ret.toFixed(1) + `% (` + bestPort.period + `)</span> · <span style="color:#dc3545;">Worst: ` + worstPort.ret.toFixed(1) + `% (` + worstPort.period + `)</span></div>
            <div style="font-size:11px;margin-top:2px;">Win: ` + portWinRate + `/` + numMonths + ` (` + (portWinRate/numMonths*100).toFixed(0) + `%) · <span style="color:#28a745;">Win streak: ` + portWinStreak + `mo</span> · <span style="color:#dc3545;">Lose streak: ` + portLoseStreak + `mo</span></div>
        </div>
        <div class="summary-card s4">
            <div class="label">Momentum + Leverage (2x ETFs when available)</div>
            <div class="value">$` + levValue.toLocaleString(undefined,{{maximumFractionDigits:0}}) + `</div>
            <div style="font-size:12px;color:#555;margin-top:4px;">` + levMultiple.toFixed(1) + `x · CAGR ` + (levCAGR*100).toFixed(1) + `% · <span style="color:#dc3545;">Max DD -` + (levMaxDD*100).toFixed(1) + `%</span></div>
            <div style="font-size:11px;margin-top:3px;"><span style="color:#28a745;">Best: +` + bestLev.ret.toFixed(1) + `% (` + bestLev.period + `)</span> · <span style="color:#dc3545;">Worst: ` + worstLev.ret.toFixed(1) + `% (` + worstLev.period + `)</span></div>
        </div>
        <div class="summary-card s2">
            <div class="label">QQQ Buy & Hold</div>
            <div class="value">$` + qqqValue.toLocaleString(undefined,{{maximumFractionDigits:0}}) + `</div>
            <div style="font-size:12px;color:#555;margin-top:4px;">` + qqqMultiple.toFixed(1) + `x · CAGR ` + (qqqCAGR*100).toFixed(1) + `% · <span style="color:#dc3545;">Max DD -` + (qqqMaxDD*100).toFixed(1) + `%</span></div>
            <div style="font-size:11px;margin-top:3px;"><span style="color:#28a745;">Best: +` + bestQQQ.ret.toFixed(1) + `% (` + bestQQQ.period + `)</span> · <span style="color:#dc3545;">Worst: ` + worstQQQ.ret.toFixed(1) + `% (` + worstQQQ.period + `)</span></div>
            <div style="font-size:11px;margin-top:2px;">Win: ` + qqqWinRate + `/` + numMonths + ` (` + (qqqWinRate/numMonths*100).toFixed(0) + `%) · <span style="color:#28a745;">Win streak: ` + qqqWinStreak + `mo</span> · <span style="color:#dc3545;">Lose streak: ` + qqqLoseStreak + `mo</span></div>
        </div>
    </div>`;
    
    // Chart
    const labels = results.map(r => r.start.substring(0,7));
    const portData = results.map(r => r.cumPort);
    const qqqData = results.map(r => r.cumQQQ);
    const levData = results.map(r => r.cumLev);
    const investedData = results.map(r => r.totalInvested);
    
    if (chart) chart.destroy();
    chart = new Chart(document.getElementById('chart'), {{
        type: 'line',
        data: {{
            labels: labels,
            datasets: [
                {{ label: 'Momentum Strategy', data: portData, borderColor: '#1f77b4', borderWidth: 1.5, pointRadius: 0, fill: false }},
                {{ label: 'Momentum + Leverage', data: levData, borderColor: '#9c27b0', borderWidth: 1.5, pointRadius: 0, fill: false }},
                {{ label: 'QQQ Buy & Hold', data: qqqData, borderColor: '#ff7f0e', borderWidth: 1.5, pointRadius: 0, fill: false }},
                {{ label: 'Total Invested', data: investedData, borderColor: '#999', borderWidth: 1, borderDash: [4,4], pointRadius: 0, fill: false }},
            ]
        }},
        options: {{
            responsive: true,
            maintainAspectRatio: false,
            interaction: {{ mode: 'index', intersect: false }},
            scales: {{
                y: {{ type: 'logarithmic', title: {{ display: true, text: 'Portfolio Value ($)' }} }},
                x: {{ ticks: {{ maxTicksLimit: 20, font: {{ size: 10 }} }} }}
            }},
            plugins: {{ legend: {{ position: 'top' }} }}
        }}
    }});
    
    // Yearly returns bar chart
    const yearlyReturns = {{}};
    const yearlyQQQ = {{}};
    const yearlyLev = {{}};
    for (const r of results) {{
        const year = r.start.substring(0,4);
        if (!yearlyReturns[year]) {{ yearlyReturns[year] = 1; yearlyQQQ[year] = 1; yearlyLev[year] = 1; }}
        yearlyReturns[year] *= (1 + r.portRet/100);
        if (r.qqqRet !== null) yearlyQQQ[year] *= (1 + r.qqqRet/100);
        const levR = r.levRet !== null ? r.levRet : r.portRet;
        yearlyLev[year] *= (1 + levR/100);
    }}
    const yearLabels = Object.keys(yearlyReturns).sort();
    const yearPortRets = yearLabels.map(y => ((yearlyReturns[y] - 1) * 100));
    const yearQQQRets = yearLabels.map(y => ((yearlyQQQ[y] - 1) * 100));
    const yearLevRets = yearLabels.map(y => ((yearlyLev[y] - 1) * 100));
    
    if (window.yearlyChartInstance) window.yearlyChartInstance.destroy();
    window.yearlyChartInstance = new Chart(document.getElementById('yearlyChart'), {{
        type: 'bar',
        data: {{
            labels: yearLabels,
            datasets: [
                {{ label: 'Momentum', data: yearPortRets, backgroundColor: yearPortRets.map(v => v >= 0 ? '#1f77b4' : '#aec7e8') }},
                {{ label: 'Momentum(lev)', data: yearLevRets, backgroundColor: yearLevRets.map(v => v >= 0 ? '#9c27b0' : '#ce93d8') }},
                {{ label: 'QQQ', data: yearQQQRets, backgroundColor: yearQQQRets.map(v => v >= 0 ? '#ff7f0e' : '#ffbb78') }},
            ]
        }},
        options: {{
            responsive: true,
            maintainAspectRatio: false,
            plugins: {{
                legend: {{ position: 'top' }},
                title: {{ display: true, text: 'Annual Returns (%)' }},
                datalabels: {{ display: false }}
            }},
            scales: {{ y: {{ ticks: {{ callback: v => v + '%' }} }} }}
        }},
        plugins: [{{
            afterDatasetsDraw(chart) {{
                const ctx = chart.ctx;
                ctx.font = '7px sans-serif';
                ctx.textAlign = 'center';
                chart.data.datasets.forEach((dataset, i) => {{
                    const meta = chart.getDatasetMeta(i);
                    meta.data.forEach((bar, index) => {{
                        const value = dataset.data[index];
                        if (value === undefined || value === null) return;
                        const label = value.toFixed(0) + '%';
                        ctx.fillStyle = '#333';
                        const y = value >= 0 ? bar.y - 2 : bar.y + 9;
                        ctx.fillText(label, bar.x, y);
                    }});
                }});
            }}
        }}]
    }});
    
    // Stock stats: best/worst performers, hold time
    const stockData = {{}};
    for (let i = 0; i < filtered.length; i++) {{
        const r = filtered[i];
        for (const [ticker, wt] of Object.entries(r.holdings)) {{
            if (!stockData[ticker]) stockData[ticker] = {{ totalRet: 0, totalDollar: 0, months: 0, bestMonth: -Infinity, worstMonth: Infinity, holdStreaks: [], currentStreak: 0 }};
            const ret = r.returns[ticker] || 0;
            const dollarInvested = (i === 0 ? initial : results[i-1].cumPort) * wt / 100;
            const dollarPnL = dollarInvested * ret / 100;
            stockData[ticker].totalRet += ret;
            stockData[ticker].totalDollar += dollarPnL;
            stockData[ticker].months++;
            if (ret > stockData[ticker].bestMonth) stockData[ticker].bestMonth = ret;
            if (ret < stockData[ticker].worstMonth) stockData[ticker].worstMonth = ret;
        }}
    }}
    
    // Calculate max continuous hold and its cumulative return for each stock
    for (const ticker of Object.keys(stockData)) {{
        let streak = 0;
        let maxStreak = 0;
        let streakReturn = 1;
        let maxStreakReturn = 0;
        let currentStreakReturn = 1;
        for (const r of filtered) {{
            if (r.holdings[ticker]) {{
                streak++;
                const ret = r.returns[ticker] || 0;
                currentStreakReturn *= (1 + ret/100);
                if (streak > maxStreak) {{
                    maxStreak = streak;
                    maxStreakReturn = (currentStreakReturn - 1) * 100;
                }}
            }} else {{
                streak = 0;
                currentStreakReturn = 1;
            }}
        }}
        stockData[ticker].maxContinuous = maxStreak;
        stockData[ticker].maxStreakReturn = maxStreakReturn;
    }}
    
    const stockArr = Object.entries(stockData).map(([t, d]) => ({{ticker: t, ...d, avgRet: d.totalRet / d.months}}));
    
    // Store globally for sorting
    window._stockArr = stockArr;
    
    function renderStockTable(sortKey, sortDir) {{
        // Filter out non-stock entries
        const validStocks = window._stockArr.filter(s => !s.ticker.includes('Return') && !s.ticker.includes('QQQ'));
        const sorted = [...validStocks].sort((a,b) => sortDir === 'desc' ? b[sortKey] - a[sortKey] : a[sortKey] - b[sortKey]);
        let html = '<h4>Stock Performance Summary</h4>';
        html += '<div style="max-height:400px;overflow-y:auto;"><table class="stats-table" id="stockSortTable"><thead><tr>';
        html += '<th data-key="ticker" data-type="str">Ticker</th>';
        html += '<th data-key="totalDollar" data-type="num">$ P&L</th>';
        html += '<th data-key="avgRet" data-type="num">Avg Ret/Mo</th>';
        html += '<th data-key="bestMonth" data-type="num">Max Gain</th>';
        html += '<th data-key="worstMonth" data-type="num">Max Loss</th>';
        html += '<th data-key="months" data-type="num">Months Held</th>';
        html += '<th data-key="maxContinuous" data-type="num">Max Streak</th>';
        html += '<th data-key="maxStreakReturn" data-type="num">Streak Ret</th>';
        html += '</tr></thead><tbody>';
        for (const s of sorted) {{
            const pnlColor = s.totalDollar >= 0 ? '#28a745' : '#dc3545';
            const pnlSign = s.totalDollar >= 0 ? '+' : '-';
            html += `<tr><td><strong>${{s.ticker}}</strong></td>`;
            html += `<td style="color:${{pnlColor}};font-weight:bold;">${{pnlSign}}$${{Math.abs(s.totalDollar).toLocaleString(undefined,{{maximumFractionDigits:0}})}}</td>`;
            html += `<td>${{s.avgRet.toFixed(1)}}%</td>`;
            html += `<td style="color:${{s.bestMonth >= 0 ? '#28a745' : '#dc3545'}};">${{s.bestMonth.toFixed(1)}}%</td>`;
            html += `<td style="color:${{s.worstMonth < 0 ? '#dc3545' : '#28a745'}};">${{s.worstMonth.toFixed(1)}}%</td>`;
            html += `<td>${{s.months}}</td>`;
            html += `<td>${{s.maxContinuous}}</td>`;
            html += `<td style="color:${{s.maxStreakReturn >= 0 ? '#28a745' : '#dc3545'}};">${{s.maxStreakReturn.toFixed(1)}}%</td></tr>`;
        }}
        html += '</tbody></table></div>';
        document.getElementById('stockStats').innerHTML = html;
        
        // Attach sort handlers
        document.querySelectorAll('#stockSortTable th').forEach(th => {{
            th.addEventListener('click', () => {{
                const key = th.dataset.key;
                const type = th.dataset.type;
                // Toggle direction
                const newDir = (key === window._lastSortKey && window._lastSortDir === 'desc') ? 'asc' : 'desc';
                window._lastSortKey = key;
                window._lastSortDir = newDir;
                if (type === 'str') {{
                    const strSorted = [...window._stockArr].sort((a,b) => newDir === 'desc' ? b.ticker.localeCompare(a.ticker) : a.ticker.localeCompare(b.ticker));
                    window._stockArr = window._stockArr; // keep original
                    renderStockTable(key === 'ticker' ? 'ticker' : key, newDir);
                }} else {{
                    renderStockTable(key, newDir);
                }}
            }});
        }});
    }}
    
    window._lastSortKey = 'totalDollar';
    window._lastSortDir = 'desc';
    renderStockTable('totalDollar', 'desc');
    
    // Table
    let html = '<table><thead><tr><th>Period</th><th>Port Ret</th><th>Lev Ret</th><th>QQQ Ret</th><th>Port Value</th><th>Lev Value</th><th>QQQ Value</th><th>Chg</th><th>Swaps</th><th>Holdings</th><th>Bench (4-10)</th></tr></thead><tbody>';
    let prevHoldings = new Set();
    for (const r of results) {{
        const portClass = r.portRet >= 0 ? 'pos' : 'neg';
        const qqqClass = (r.qqqRet||0) >= 0 ? 'pos' : 'neg';
        
        // Calculate ticker changes
        const currentHoldings = new Set(Object.keys(r.holdings).filter(t => !t.includes('Return') && !t.includes('QQQ')));
        const added = [...currentHoldings].filter(t => !prevHoldings.has(t)).length;
        const removed = [...prevHoldings].filter(t => !currentHoldings.has(t)).length;
        const changes = Math.max(added, removed);
        prevHoldings = currentHoldings;
        
        // Build holdings tags
        let holdingsHtml = '';
        const sortedHoldings = Object.entries(r.holdings).sort((a,b) => b[1]-a[1]).filter(([t]) => !t.includes('Return') && !t.includes('QQQ'));
        for (const [ticker, wt] of sortedHoldings) {{
            const ret = r.returns[ticker];
            const retStr = ret !== undefined ? ` ${{ret > 0 ? '+' : ''}}${{ret.toFixed(1)}}%` : '';
            const retClass = ret > 0 ? 'pos' : (ret < 0 ? 'neg' : '');
            const wtStr = sortedHoldings.length > 5 ? ` ${{wt.toFixed(1)}}%` : '';
            holdingsHtml += `<span class="tag tag-held">${{ticker}}${{wtStr}}<span class="${{retClass}}">${{retStr}}</span></span> `;
        }}
        
        // Build bench (ranks 4-7) returns
        const bench = r.benchReturns || {{}};
        const benchHtml = Object.entries(bench).map(([ticker, ret]) => {{
            const retClass = ret > 0 ? 'pos' : (ret < 0 ? 'neg' : '');
            const retStr = (ret > 0 ? '+' : '') + ret.toFixed(1) + '%';
            return `<span class="tag" style="background:#e2e3e5;color:#383d41;">${{ticker}} <span class="${{retClass}}">${{retStr}}</span></span>`;
        }}).join(' ') || '-';
        
        // Build leveraged holdings info
        const levRet = r.levRet !== null ? r.levRet : r.portRet;
        const levClass = levRet >= 0 ? 'pos' : 'neg';
        
        html += `<tr>
            <td>${{r.end.substring(0,7)}}</td>
            <td class="${{portClass}}">${{r.portRet > 0 ? '+' : ''}}${{r.portRet.toFixed(1)}}%</td>
            <td class="${{levClass}}">${{levRet > 0 ? '+' : ''}}${{levRet.toFixed(1)}}%</td>
            <td class="${{qqqClass}}">${{r.qqqRet !== null ? (r.qqqRet > 0 ? '+' : '') + r.qqqRet.toFixed(1) + '%' : '-'}}</td>
            <td>$${{r.cumPort.toLocaleString(undefined,{{maximumFractionDigits:0}})}}</td>
            <td>$${{r.cumLev.toLocaleString(undefined,{{maximumFractionDigits:0}})}}</td>
            <td>$${{r.cumQQQ.toLocaleString(undefined,{{maximumFractionDigits:0}})}}</td>
            <td>${{changes > 0 ? changes : '-'}}</td>
            <td style="font-size:10px;">${{r.changes || '-'}}</td>
            <td style="text-align:left">${{holdingsHtml}}</td>
            <td style="text-align:left">${{benchHtml}}</td>
        </tr>`;
    }}
    html += '</tbody></table>';
    document.getElementById('tableContainer').innerHTML = html;
    
    // Distribution histogram of individual stock-month returns
    const allReturns = [];
    for (const r of results) {{
        for (const [ticker, ret] of Object.entries(r.returns)) {{
            if (!ticker.includes('Return') && !ticker.includes('QQQ') && ret !== undefined) {{
                allReturns.push(ret);
            }}
        }}
    }}
    
    const bins = [[-60,-40],[-40,-20],[-20,0],[0,20],[20,40],[40,60],[60,100]];
    const binLabels = ['-60 to -40%','-40 to -20%','-20 to 0%','0 to +20%','+20 to +40%','+40 to +60%','+60%+'];
    const binCounts = bins.map(([lo,hi]) => allReturns.filter(r => r >= lo && r < hi).length);
    const positive = allReturns.filter(r => r > 0).length;
    const mean = allReturns.reduce((a,b) => a+b, 0) / allReturns.length;
    
    let distHtml = '<div id="distChart" style="background:white;border-radius:8px;padding:15px;margin-top:15px;box-shadow:0 1px 3px rgba(0,0,0,0.1);">';
    distHtml += '<h4 style="margin:0 0 10px 0;">Monthly Stock Return Distribution (' + allReturns.length + ' stock-months)</h4>';
    distHtml += '<div style="display:flex;gap:15px;margin-bottom:10px;font-size:12px;color:#555;">';
    distHtml += '<span>Win rate: <strong>' + positive + '/' + allReturns.length + ' (' + (positive/allReturns.length*100).toFixed(0) + '%)</strong></span>';
    distHtml += '<span>Mean: <strong>' + mean.toFixed(1) + '%</strong>/month</span>';
    distHtml += '<span>Min: <strong>' + Math.min(...allReturns).toFixed(1) + '%</strong></span>';
    distHtml += '<span>Max: <strong>+' + Math.max(...allReturns).toFixed(1) + '%</strong></span>';
    distHtml += '</div>';
    distHtml += '<div style="display:flex;align-items:end;gap:4px;height:120px;">';
    const maxCount = Math.max(...binCounts);
    binCounts.forEach((count, i) => {{
        const height = (count / maxCount) * 100;
        const color = bins[i][0] < 0 ? '#dc354580' : '#28a74580';
        distHtml += '<div style="flex:1;display:flex;flex-direction:column;align-items:center;">';
        distHtml += '<span style="font-size:10px;font-weight:bold;">' + count + '</span>';
        distHtml += '<div style="width:100%;height:' + height + 'px;background:' + color + ';border-radius:3px 3px 0 0;"></div>';
        distHtml += '<span style="font-size:9px;color:#666;margin-top:4px;">' + binLabels[i] + '</span>';
        distHtml += '</div>';
    }});
    distHtml += '</div></div>';
    // Remove old distribution chart if exists
    const oldDist = document.getElementById('distChart');
    if (oldDist) oldDist.remove();
    
    document.getElementById('tableContainer').insertAdjacentHTML('afterend', distHtml);
}}

let isLogScale = true;
function toggleScale() {{
    isLogScale = !isLogScale;
    document.getElementById('scaleToggle').textContent = isLogScale ? 'Linear' : 'Log';
    if (chart) {{
        chart.options.scales.y.type = isLogScale ? 'logarithmic' : 'linear';
        chart.update();
    }}
}}

// Initial render
recalculate();
</script>
</body></html>"""

with open("momentum_backtest_dashboard.html", "w") as f:
    f.write(html)

print("Generated: nasdaq_momentum/momentum_backtest_dashboard.html")
print(f"  Data points: {len(data)} months")
print(f"  Tickers tracked: {len(all_tickers)}")
