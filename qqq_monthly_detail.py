"""
Generate an interactive HTML table with dynamic start/end date filtering.
All computation happens in JavaScript so the user can change dates without regenerating.
"""

import pandas as pd
import numpy as np
import json

df = pd.read_csv(
    "~/Downloads/QQQ ETF Stock Price History (2).csv",
    thousands=","
)
df["Date"] = pd.to_datetime(df["Date"], format="%m/%d/%Y")
df = df.sort_values("Date").reset_index(drop=True)
df["Price"] = pd.to_numeric(df["Price"].astype(str).str.replace(",", ""), errors="coerce")

# Export raw monthly data as JSON — JS will compute everything dynamically
data = []
for _, row in df.iterrows():
    data.append({
        "date": row["Date"].strftime("%Y-%m"),
        "dateLabel": row["Date"].strftime("%b %Y"),
        "price": round(row["Price"], 2),
    })

data_json = json.dumps(data)

html = """<!DOCTYPE html>
<html>
<head>
<title>QQQ V2 Fixed Strategy — Dynamic Monthly Detail</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 20px; background: #f8f9fa; }
h1 { color: #333; margin-bottom: 10px; }
.controls { background: white; padding: 15px; border-radius: 8px; margin-bottom: 15px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); display: flex; align-items: center; gap: 20px; flex-wrap: wrap; }
.controls label { font-size: 14px; font-weight: bold; }
.controls select, .controls input { padding: 6px 10px; border: 1px solid #ddd; border-radius: 4px; font-size: 14px; }
.summary { background: white; padding: 15px; border-radius: 8px; margin-bottom: 15px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); display: flex; gap: 30px; flex-wrap: wrap; }
.summary .item { font-size: 14px; }
.summary .item b { display: block; font-size: 12px; color: #666; margin-bottom: 2px; }
.summary .item .val { font-size: 18px; font-weight: bold; }
.buy { background-color: #d4edda !important; }
.sell { background-color: #f8d7da !important; }
.hold { background-color: #fff3cd !important; }
table { border-collapse: collapse; width: 100%; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1); font-size: 13px; }
th { background: #343a40; color: white; padding: 10px 8px; text-align: right; position: sticky; top: 0; z-index: 10; }
th:nth-child(1), th:nth-child(5) { text-align: left; }
td { padding: 7px 8px; border-bottom: 1px solid #eee; text-align: right; white-space: nowrap; }
td:nth-child(1), td:nth-child(5) { text-align: left; }
tr:hover { background: #e9ecef !important; }
.pos { color: #28a745; font-weight: bold; }
.neg { color: #dc3545; font-weight: bold; }
.filter-bar { margin-bottom: 10px; display: flex; gap: 8px; align-items: center; }
.filter-bar button { padding: 6px 14px; border: 1px solid #ddd; border-radius: 4px; cursor: pointer; background: white; font-size: 13px; }
.filter-bar button.active { background: #343a40; color: white; }
</style>
</head>
<body>
<h1>QQQ V2 Fixed Strategy — Monthly Detail</h1>

<div class="controls">
    <div><label>Start:</label> <input type="month" id="startDate" value="1999-04"></div>
    <div><label>End:</label> <input type="month" id="endDate" value="2026-06"></div>
    <div><button onclick="recalculate()" style="padding:8px 20px; background:#343a40; color:white; border:none; border-radius:4px; cursor:pointer; font-size:14px;">Apply</button></div>
</div>

<div class="summary" id="summary"></div>

<div id="chartContainer" style="background:white; border-radius:8px; padding:15px; margin-bottom:15px; box-shadow:0 1px 3px rgba(0,0,0,0.1); height:350px;">
    <canvas id="rollingChart"></canvas>
</div>

<div class="filter-bar">
    <button class="active" onclick="filterRows('all', this)">All</button>
    <button onclick="filterRows('Buy', this)">Buy Only</button>
    <button onclick="filterRows('Sell', this)">Sell Only</button>
    <button onclick="filterRows('Hold', this)">Hold Only</button>
</div>

<table>
<thead><tr>
    <th>Date</th><th>Price</th><th>1Y Rolling</th><th>Drawdown</th>
    <th>Action</th><th>Sig Shares</th><th>Sig Invested</th><th>Sig Sold</th>
    <th>Sig Portfolio</th><th>Sig Total</th>
    <th>DCA Shares</th><th>DCA Invested</th><th>DCA Value</th><th>Sig vs DCA</th>
</tr></thead>
<tbody id="tbody"></tbody>
</table>

<script>
const RAW_DATA = """ + data_json + """;

function getSignal(rolling1Y, drawdown) {
    if (rolling1Y === null) return { action: "Buy", amount: 1000 };
    if (rolling1Y <= -40) return { action: "Buy", amount: 4000 };
    if (rolling1Y <= -20) return drawdown <= -30 ? { action: "Buy", amount: 4000 } : { action: "Buy", amount: 3000 };
    if (rolling1Y < 0) return { action: "Buy", amount: 2000 };
    if (rolling1Y < 20) return { action: "Buy", amount: 1000 };
    if (rolling1Y < 30) return { action: "Hold", amount: 0 };
    if (drawdown <= -20) return { action: "Hold", amount: 0 };
    if (rolling1Y < 40) return { action: "Sell", amount: 1000 };
    if (rolling1Y < 60) return drawdown > -5 ? { action: "Sell", amount: 2000 } : { action: "Sell", amount: 1000 };
    return { action: "Sell", amount: 4000 };
}

function fmt(n) { return "$" + n.toLocaleString("en-US", {maximumFractionDigits: 0}); }
function fmtDiff(n) { return (n >= 0 ? "+" : "") + fmt(n); }

function recalculate() {
    const startVal = document.getElementById("startDate").value;
    const endVal = document.getElementById("endDate").value;

    // Filter data to range
    const filtered = RAW_DATA.filter(d => d.date >= startVal && d.date <= endVal);
    if (filtered.length === 0) return;

    // Compute rolling returns relative to filtered start
    // But we need to look back 12 months from start for rolling calc
    // Find the index in RAW_DATA for lookback
    const startIdx = RAW_DATA.findIndex(d => d.date === filtered[0].date);

    let dcaShares = 0, dcaInvested = 0;
    let sigShares = 0, sigInvested = 0, sigSold = 0;
    let peak = 0;
    let rows = [];

    for (let i = 0; i < filtered.length; i++) {
        const globalIdx = startIdx + i;
        const price = filtered[i].price;

        // Peak from the START of simulation (not all-time)
        if (price > peak) peak = price;
        const drawdown = (price / peak - 1) * 100;

        // 1Y rolling: need price 12 months ago relative to simulation start
        let rolling1Y = null;
        if (i >= 12) {
            const pricePast = filtered[i - 12].price;
            rolling1Y = (price / pricePast - 1) * 100;
        }

        const signal = getSignal(rolling1Y, drawdown);

        // DCA
        dcaShares += 1000 / price;
        dcaInvested += 1000;
        const dcaValue = dcaShares * price;

        // Signal
        if (signal.action === "Buy") {
            sigShares += signal.amount / price;
            sigInvested += signal.amount;
        } else if (signal.action === "Sell") {
            const sharesToSell = Math.min(signal.amount / price, sigShares);
            const actualSell = sharesToSell * price;
            sigShares -= sharesToSell;
            sigSold += actualSell;
        }

        const sigPortfolio = sigShares * price;
        const sigTotal = sigPortfolio + sigSold;
        const diff = sigTotal - dcaValue;

        rows.push({
            dateLabel: filtered[i].dateLabel,
            price, rolling1Y, drawdown,
            action: signal.action, amount: signal.amount,
            sigShares, sigInvested, sigSold, sigPortfolio, sigTotal,
            dcaShares, dcaInvested, dcaValue, diff
        });
    }

    // Update summary
    const last = rows[rows.length - 1];
    const diffClass = last.diff >= 0 ? "pos" : "neg";
    const sigXIRR = last.sigInvested > 0 ? ((last.sigTotal / last.sigInvested - 1) * 100).toFixed(0) : 0;
    const dcaXIRR = last.dcaInvested > 0 ? ((last.dcaValue / last.dcaInvested - 1) * 100).toFixed(0) : 0;
    document.getElementById("summary").innerHTML = `
        <div class="item"><b>Period</b><span class="val">${rows[0].dateLabel} — ${last.dateLabel} (${rows.length} mo)</span></div>
        <div class="item"><b>Signal Total</b><span class="val">${fmt(last.sigTotal)}</span></div>
        <div class="item"><b>Signal Invested</b><span class="val">${fmt(last.sigInvested)}</span></div>
        <div class="item"><b>Signal Return</b><span class="val">${sigXIRR}%</span></div>
        <div class="item"><b>DCA Value</b><span class="val">${fmt(last.dcaValue)}</span></div>
        <div class="item"><b>DCA Invested</b><span class="val">${fmt(last.dcaInvested)}</span></div>
        <div class="item"><b>DCA Return</b><span class="val">${dcaXIRR}%</span></div>
        <div class="item"><b>Signal vs DCA</b><span class="val ${diffClass}">${fmtDiff(last.diff)}</span></div>
    `;

    // Build table
    const tbody = document.getElementById("tbody");
    tbody.innerHTML = rows.map(r => {
        const actionClass = r.action.toLowerCase();
        const dc = r.diff >= 0 ? "pos" : "neg";
        const actionStr = r.amount > 0 ? `${r.action} $${r.amount.toLocaleString()}` : "Hold";
        const r1y = r.rolling1Y !== null ? r.rolling1Y.toFixed(1) + "%" : "—";
        return `<tr class="${actionClass}" data-action="${r.action}">
            <td>${r.dateLabel}</td>
            <td>$${r.price.toFixed(2)}</td>
            <td>${r1y}</td>
            <td>${r.drawdown.toFixed(1)}%</td>
            <td><b>${actionStr}</b></td>
            <td>${r.sigShares.toFixed(1)}</td>
            <td>${fmt(r.sigInvested)}</td>
            <td>${fmt(r.sigSold)}</td>
            <td>${fmt(r.sigPortfolio)}</td>
            <td>${fmt(r.sigTotal)}</td>
            <td>${r.dcaShares.toFixed(1)}</td>
            <td>${fmt(r.dcaInvested)}</td>
            <td>${fmt(r.dcaValue)}</td>
            <td class="${dc}">${fmtDiff(r.diff)}</td>
        </tr>`;
    }).join("");

    // Draw 1Y Rolling Return chart
    drawChart(rows);
}

let chartInstance = null;
function drawChart(rows) {
    const ctx = document.getElementById("rollingChart").getContext("2d");
    if (chartInstance) chartInstance.destroy();

    const labels = rows.map(r => r.dateLabel);
    const rollingData = rows.map(r => r.rolling1Y);
    const priceData = rows.map(r => r.price);
    const colors = rollingData.map(v => {
        if (v === null) return "rgba(150,150,150,0.8)";
        if (v >= 40) return "rgba(220,53,69,0.8)";
        if (v >= 30) return "rgba(255,127,14,0.8)";
        if (v >= 20) return "rgba(255,193,7,0.8)";
        if (v >= 0) return "rgba(40,167,69,0.4)";
        if (v >= -20) return "rgba(40,167,69,0.7)";
        return "rgba(40,167,69,1)";
    });

    chartInstance = new Chart(ctx, {
        type: "bar",
        data: {
            labels: labels,
            datasets: [
                {
                    label: "1Y Rolling Return (%)",
                    data: rollingData,
                    backgroundColor: colors,
                    borderWidth: 0,
                    yAxisID: "y",
                    order: 2,
                },
                {
                    label: "QQQ Price ($)",
                    data: priceData,
                    type: "line",
                    borderColor: "rgba(30,60,150,0.9)",
                    backgroundColor: "rgba(30,60,150,0.05)",
                    borderWidth: 2,
                    pointRadius: 0,
                    fill: true,
                    yAxisID: "y1",
                    order: 1,
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: "index", intersect: false },
            plugins: {
                legend: { display: true, position: "top" },
                title: { display: true, text: "QQQ Price & 1Y Rolling Return \\u2014 Green=Buy, Yellow=Hold, Orange/Red=Sell", font: { size: 14 } },
                tooltip: {
                    backgroundColor: "rgba(255,255,255,0.95)",
                    titleColor: "#333",
                    bodyColor: "#555",
                    borderColor: "#ddd",
                    borderWidth: 1,
                    padding: 12,
                    bodySpacing: 6,
                    titleFont: { size: 13, weight: "bold" },
                    bodyFont: { size: 12 },
                    displayColors: false,
                    callbacks: {
                        title: function(tooltipItems) {
                            return tooltipItems[0].label;
                        },
                        label: function(ctx) {
                            if (ctx.dataset.yAxisID === "y1") return "\\u25B6 Price:  $" + ctx.raw.toFixed(2);
                            return ctx.raw !== null ? "\\u25B6 1Y Return:  " + ctx.raw.toFixed(1) + "%" : "\\u25B6 1Y Return:  N/A";
                        },
                        afterBody: function(tooltipItems) {
                            const idx = tooltipItems[0].dataIndex;
                            const r = rows[idx];
                            const actionStr = r.amount > 0 ? r.action + " $" + r.amount.toLocaleString() : "Hold";
                            const actionIcon = r.action === "Buy" ? "\\u25B2" : r.action === "Sell" ? "\\u25BC" : "\\u25CF";
                            return [
                                "\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500",
                                actionIcon + " Action:  " + actionStr,
                                "\\u25A0 Signal Total:  " + fmt(r.sigTotal),
                                "\\u25A0 DCA Value:  " + fmt(r.dcaValue),
                                (r.diff >= 0 ? "\\u2713" : "\\u2717") + " Sig vs DCA:  " + fmtDiff(r.diff),
                            ];
                        },
                    }
                }
            },
            scales: {
                x: { ticks: { maxTicksLimit: 20, font: { size: 10 } } },
                y: {
                    position: "left",
                    title: { display: true, text: "1Y Rolling (%)" },
                    grid: { color: function(ctx) { return ctx.tick.value === 0 ? "#333" : "#eee"; } },
                    ticks: { callback: function(v) { return v + "%"; } }
                },
                y1: {
                    position: "right",
                    title: { display: true, text: "QQQ Price ($)" },
                    grid: { drawOnChartArea: false },
                    ticks: { callback: function(v) { return "$" + v; } }
                }
            }
        }
    });
}

function filterRows(action, btn) {
    document.querySelectorAll(".filter-bar button").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    document.querySelectorAll("#tbody tr").forEach(row => {
        if (action === "all" || row.dataset.action === action) { row.style.display = ""; }
        else { row.style.display = "none"; }
    });
}

// Initial load
recalculate();
</script>
</body>
</html>"""

output_path = "/Users/ajhanwa/workspace/stocks/qqq_monthly_detail.html"
with open(output_path, "w") as f:
    f.write(html)

print(f"Saved to: {output_path}")
print(f"Data points exported: {len(data)}")
