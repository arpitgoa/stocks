"""
NDX/Gold/SOX Rotation Strategy — Interactive HTML Dashboard
Strategy 3: NDX + Gold rotation
Strategy 4: NDX + Gold + SOX 3-asset rotation
"""

import pandas as pd
import json

df = pd.read_csv("ndx_gold_combined.csv")
df["Date"] = pd.to_datetime(df["Date"])
df = df.sort_values("Date").reset_index(drop=True)

data = []
for _, row in df.iterrows():
    sox = round(row["SOX_Price"], 2) if pd.notna(row["SOX_Price"]) else None
    ndx_sox = round(row["NDX_SOX_Ratio"], 4) if pd.notna(row["NDX_SOX_Ratio"]) else None
    data.append({
        "date": row["Date"].strftime("%Y-%m"),
        "dateLabel": row["Date"].strftime("%b %Y"),
        "ndx": round(row["NDX_Price"], 2),
        "gold": round(row["Gold_Price"], 2),
        "ratio": round(row["NDX_Gold_Ratio"], 4),
        "sox": sox,
        "ndxSoxRatio": ndx_sox,
    })

data_json = json.dumps(data)

js_code = r"""
const RAW_DATA = __DATA_PLACEHOLDER__;

function fmt(n) { return "$" + Math.round(n).toLocaleString("en-US"); }
function fmtDiff(n) { return (n >= 0 ? "+" : "") + fmt(n); }

function calcXIRR(cashflows, dates) {
    // cashflows: array of {amount, date} where negative = investment, positive = withdrawal/final value
    if (cashflows.length < 2) return 0;
    var d0 = dates[0];
    var years = dates.map(function(d) { return (d - d0) / (365.25 * 86400000); });
    function npv(rate) {
        var sum = 0;
        for (var i = 0; i < cashflows.length; i++) {
            sum += cashflows[i] / Math.pow(1 + rate, years[i]);
        }
        return sum;
    }
    // Bisection method
    var lo = -0.5, hi = 5.0;
    for (var iter = 0; iter < 200; iter++) {
        var mid = (lo + hi) / 2;
        if (npv(mid) > 0) lo = mid; else hi = mid;
        if (hi - lo < 0.00001) break;
    }
    return (lo + hi) / 2;
}

let chartInstance = null;

function recalculate() {
    const startVal = document.getElementById("startDate").value;
    const endVal = document.getElementById("endDate").value;
    const initialAmt = parseFloat(document.getElementById("initialAmt").value) || 0;
    const monthlyAmtRaw = document.getElementById("monthlyAmt").value;
    const monthlyAmt = monthlyAmtRaw === "" ? 1000 : parseFloat(monthlyAmtRaw);
    const ndxPct = parseFloat(document.getElementById("ndxPctSlider").value) / 100;
    const goldPct = 1 - ndxPct;
    const filtered = RAW_DATA.filter(d => d.date >= startVal && d.date <= endVal);
    if (filtered.length === 0) return;

    // Strategy 1: DCA into NDX
    let dcaShares = 0, dcaInvested = 0;
    // Strategy 3: NDX+Gold % rotation
    let s3ndx = 0, s3gold = 0, s3Invested = 0;
    // Strategy 4: NDX+Gold+SOX 3-asset rotation
    let s4ndx = 0, s4gold = 0, s4sox = 0, s4Invested = 0;
    // XIRR cashflow tracking
    var dcaCF = [], dcaDates = [], s3CF = [], s3Dates = [], s4CF = [], s4Dates = [];

    // Initial investment
    if (initialAmt > 0 && filtered.length > 0) {
        var fn = filtered[0].ndx, fg = filtered[0].gold;
        dcaShares += initialAmt / fn;
        dcaInvested += initialAmt;
        s3ndx += initialAmt * ndxPct / fn;
        s3gold += initialAmt * goldPct / fg;
        s3Invested += initialAmt;
        // S4: split 3 ways if SOX available
        if (filtered[0].sox) {
            s4ndx += initialAmt * 0.34 / fn;
            s4gold += initialAmt * 0.33 / fg;
            s4sox += initialAmt * 0.33 / filtered[0].sox;
        } else {
            s4ndx += initialAmt * ndxPct / fn;
            s4gold += initialAmt * goldPct / fg;
        }
        s4Invested += initialAmt;
    }

    var rows = [];
    var half = monthlyAmt / 2;
    var third = monthlyAmt / 3;

    for (var i = 0; i < filtered.length; i++) {
        var d = filtered[i];
        var r = d.ratio;
        var ns = d.ndxSoxRatio;

        // DCA
        dcaShares += monthlyAmt / d.ndx;
        dcaInvested += monthlyAmt;
        var dcaValue = dcaShares * d.ndx;
        var monthDate = new Date(d.date + "-01");
        dcaCF.push(-monthlyAmt); dcaDates.push(monthDate);
        s3CF.push(-monthlyAmt); s3Dates.push(monthDate);
        s4CF.push(-monthlyAmt); s4Dates.push(monthDate);

        // === Strategy 3: NDX+Gold rotation ===
        var s3ndxVal = s3ndx * d.ndx;
        var s3goldVal = s3gold * d.gold;
        var s3rot = 0, s3dir = "";

        if (r >= 9) {
            s3rot = s3ndxVal * 0.05; s3ndx -= s3rot/d.ndx; s3gold += s3rot/d.gold; s3dir = "5%NDX->Gold";
            s3gold += monthlyAmt/d.gold; s3Invested += monthlyAmt;
        } else if (r >= 7) {
            s3rot = s3ndxVal * 0.02; s3ndx -= s3rot/d.ndx; s3gold += s3rot/d.gold; s3dir = "2%NDX->Gold";
            s3gold += monthlyAmt/d.gold; s3Invested += monthlyAmt;
        } else if (r >= 4) {
            s3dir = "None";
            s3ndx += half/d.ndx; s3gold += half/d.gold; s3Invested += monthlyAmt;
        } else if (r >= 2.5) {
            s3rot = s3goldVal * 0.02; s3gold -= s3rot/d.gold; s3ndx += s3rot/d.ndx; s3dir = "2%Gold->NDX";
            s3ndx += monthlyAmt/d.ndx; s3Invested += monthlyAmt;
        } else {
            s3rot = s3goldVal * 0.05; s3gold -= s3rot/d.gold; s3ndx += s3rot/d.ndx; s3dir = "5%Gold->NDX";
            s3ndx += monthlyAmt/d.ndx; s3Invested += monthlyAmt;
        }
        var s3Total = s3ndx*d.ndx + s3gold*d.gold;

        // === Strategy 4: NDX+Gold+SOX 3-asset rotation ===
        var s4ndxVal = s4ndx * d.ndx;
        var s4goldVal = s4gold * d.gold;
        var s4soxVal = d.sox ? s4sox * d.sox : 0;
        var s4rot1 = 0, s4rot2 = 0, s4dir = "";

        if (d.sox && ns !== null) {
            if (r >= 9) {
                // Sell 5% of ALL tech -> Gold
                s4rot1 = s4ndxVal * 0.05; s4ndx -= s4rot1/d.ndx; s4gold += s4rot1/d.gold;
                s4rot2 = s4soxVal * 0.05; s4sox -= s4rot2/d.sox; s4gold += s4rot2/d.gold;
                s4dir = "5%NDX->Gold + 5%SOX->Gold";
            } else if (r >= 7) {
                // Sell 2% of ALL tech -> Gold
                s4rot1 = s4ndxVal * 0.02; s4ndx -= s4rot1/d.ndx; s4gold += s4rot1/d.gold;
                s4rot2 = s4soxVal * 0.02; s4sox -= s4rot2/d.sox; s4gold += s4rot2/d.gold;
                s4dir = "2%NDX->Gold + 2%SOX->Gold";
            } else if (r < 2.5) {
                // Sell 5% Gold -> NDX only (ignore SOX)
                s4rot1 = s4goldVal * 0.05; s4gold -= s4rot1/d.gold; s4ndx += s4rot1/d.ndx;
                s4dir = "5%Gold->NDX";
            } else if (r < 4) {
                // Sell 2% Gold -> NDX only (ignore SOX)
                s4rot1 = s4goldVal * 0.02; s4gold -= s4rot1/d.gold; s4ndx += s4rot1/d.ndx;
                s4dir = "2%Gold->NDX";
            } else {
                // NDX/Gold neutral (4-7): use NDX/SOX for tech rotation
                if (ns >= 6) {
                    s4rot2 = s4ndxVal * 0.03; s4ndx -= s4rot2/d.ndx; s4sox += s4rot2/d.sox;
                    s4dir = "3%NDX->SOX";
                } else if (ns >= 5) {
                    s4rot2 = s4ndxVal * 0.02; s4ndx -= s4rot2/d.ndx; s4sox += s4rot2/d.sox;
                    s4dir = "2%NDX->SOX";
                } else if (ns < 2.5) {
                    s4rot2 = s4soxVal * 0.05; s4sox -= s4rot2/d.sox; s4ndx += s4rot2/d.ndx;
                    s4dir = "5%SOX->NDX";
                } else if (ns < 3) {
                    s4rot2 = s4soxVal * 0.02; s4sox -= s4rot2/d.sox; s4ndx += s4rot2/d.ndx;
                    s4dir = "2%SOX->NDX";
                } else {
                    s4dir = "None";
                }
            }
        } else {
            // No SOX data: same as S3
            if (r >= 9) {
                s4rot1 = s4ndxVal * 0.05; s4ndx -= s4rot1/d.ndx; s4gold += s4rot1/d.gold;
                s4dir = "5%NDX->Gold";
            } else if (r >= 7) {
                s4rot1 = s4ndxVal * 0.02; s4ndx -= s4rot1/d.ndx; s4gold += s4rot1/d.gold;
                s4dir = "2%NDX->Gold";
            } else if (r < 2.5) {
                s4rot1 = s4goldVal * 0.05; s4gold -= s4rot1/d.gold; s4ndx += s4rot1/d.ndx;
                s4dir = "5%Gold->NDX";
            } else if (r < 4) {
                s4rot1 = s4goldVal * 0.02; s4gold -= s4rot1/d.gold; s4ndx += s4rot1/d.ndx;
                s4dir = "2%Gold->NDX";
            } else {
                s4dir = "None";
            }
        }

        // S4 Monthly investment allocation
        if (r >= 7) {
            // Tech expensive -> all to gold
            s4gold += monthlyAmt / d.gold;
        } else if (r < 4) {
            // Tech cheap -> all to NDX (ignore SOX in downturns)
            s4ndx += monthlyAmt / d.ndx;
        } else if (d.sox && ns !== null) {
            // Neutral: use NDX/SOX to allocate between tech assets
            if (ns >= 5) {
                s4sox += (monthlyAmt*0.5)/d.sox; s4gold += (monthlyAmt*0.25)/d.gold; s4ndx += (monthlyAmt*0.25)/d.ndx;
            } else if (ns < 3) {
                s4ndx += (monthlyAmt*0.5)/d.ndx; s4gold += (monthlyAmt*0.25)/d.gold; s4sox += (monthlyAmt*0.25)/d.sox;
            } else {
                s4ndx += third/d.ndx; s4gold += third/d.gold; s4sox += third/d.sox;
            }
        } else {
            s4ndx += half/d.ndx; s4gold += half/d.gold;
        }
        s4Invested += monthlyAmt;

        var s4Total = s4ndx*d.ndx + s4goldVal + s4gold*d.gold - s4goldVal + s4gold*d.gold;
        // recalculate properly
        s4Total = s4ndx*d.ndx + s4gold*d.gold + (d.sox ? s4sox*d.sox : 0);

        // Drawdowns
        var dcaPeak = rows.reduce(function(mx,ro){return Math.max(mx, ro.dcaValue||0);}, dcaValue);
        var s3Peak = rows.reduce(function(mx,ro){return Math.max(mx, ro.s3Total||0);}, s3Total);
        var s4Peak = rows.reduce(function(mx,ro){return Math.max(mx, ro.s4Total||0);}, s4Total);
        var dcaDD = (dcaValue/dcaPeak - 1)*100;
        var s3DD = (s3Total/s3Peak - 1)*100;
        var s4DD = (s4Total/s4Peak - 1)*100;

        rows.push({
            dateLabel: d.dateLabel, ndx: d.ndx, gold: d.gold, sox: d.sox, ratio: r, ndxSoxRatio: ns,
            s3ndx: s3ndx, s3gold: s3gold, s3Total: s3Total, s3rot: s3rot, s3dir: s3dir, s3Invested: s3Invested,
            s4ndx: s4ndx, s4gold: s4gold, s4sox: s4sox, s4Total: s4Total, s4dir: s4dir, s4Invested: s4Invested,
            dcaShares: dcaShares, dcaInvested: dcaInvested, dcaValue: dcaValue,
            dcaDD: dcaDD, s3DD: s3DD, s4DD: s4DD
        });
    }

    // Summary
    var last = rows[rows.length - 1];
    var lastDate = new Date(filtered[filtered.length-1].date + "-01");
    // Terminal cashflows for XIRR
    dcaCF.push(last.dcaValue); dcaDates.push(lastDate);
    s3CF.push(last.s3Total); s3Dates.push(lastDate);
    s4CF.push(last.s4Total); s4Dates.push(lastDate);
    var dcaXIRR = (calcXIRR(dcaCF, dcaDates) * 100).toFixed(1);
    var s3XIRR = (calcXIRR(s3CF, s3Dates) * 100).toFixed(1);
    var s4XIRR = (calcXIRR(s4CF, s4Dates) * 100).toFixed(1);

    var dcaMaxDD = Math.min.apply(null, rows.map(function(r){return r.dcaDD;})).toFixed(1);
    var s3MaxDD = Math.min.apply(null, rows.map(function(r){return r.s3DD;})).toFixed(1);
    var s4MaxDD = Math.min.apply(null, rows.map(function(r){return r.s4DD;})).toFixed(1);
    var s3ndxPct = (last.s3ndx*last.ndx / last.s3Total * 100).toFixed(0);
    var s3goldPct = (last.s3gold*last.gold / last.s3Total * 100).toFixed(0);
    var s4ndxPct = last.s4Total > 0 ? (last.s4ndx*last.ndx / last.s4Total * 100).toFixed(0) : 0;
    var s4goldPct = last.s4Total > 0 ? (last.s4gold*last.gold / last.s4Total * 100).toFixed(0) : 0;
    var s4soxPct = last.s4Total > 0 && last.sox ? (last.s4sox*last.sox / last.s4Total * 100).toFixed(0) : 0;

    document.getElementById("summary").innerHTML =
        '<div class="summary-grid">' +
        '<div class="summary-card s1"><div class="label">1. DCA NDX</div><div class="value">' + fmt(last.dcaValue) + '</div><div class="label">Inv: ' + fmt(last.dcaInvested) + ' | XIRR: ' + dcaXIRR + '% | Max DD: <span class="neg">' + dcaMaxDD + '%</span></div></div>' +
        '<div class="summary-card s3"><div class="label">3. NDX+Gold Rotation</div><div class="value">' + fmt(last.s3Total) + '</div><div class="label">NDX ' + s3ndxPct + '% Gold ' + s3goldPct + '% | XIRR: ' + s3XIRR + '% | Max DD: <span class="neg">' + s3MaxDD + '%</span></div></div>' +
        '<div class="summary-card s4"><div class="label">4. NDX+Gold+SOX Rotation</div><div class="value">' + fmt(last.s4Total) + '</div><div class="label">NDX ' + s4ndxPct + '% Gold ' + s4goldPct + '% SOX ' + s4soxPct + '% | XIRR: ' + s4XIRR + '% | Max DD: <span class="neg">' + s4MaxDD + '%</span></div></div>' +
        '<div class="summary-card"><div class="label">NDX/Gold</div><div class="value">' + last.ratio.toFixed(2) + '</div><div class="label">NDX/SOX: ' + (last.ndxSoxRatio ? last.ndxSoxRatio.toFixed(2) : "N/A") + '</div></div>' +
        '<div class="summary-card"><div class="label">Period</div><div class="value">' + rows[0].dateLabel + ' \u2014 ' + last.dateLabel + '</div><div class="label">' + rows.length + ' months</div></div>' +
        '</div>';

    // Table
    var tbody = document.getElementById("tbody");
    var html = "";
    for (var i = 0; i < rows.length; i++) {
        var ro = rows[i];
        var dc3 = (ro.s3Total - ro.dcaValue) >= 0 ? "pos" : "neg";
        var dc4 = (ro.s4Total - ro.dcaValue) >= 0 ? "pos" : "neg";
        var nsStr = ro.ndxSoxRatio ? ro.ndxSoxRatio.toFixed(2) : "\u2014";
        html += '<tr>' +
            '<td>' + ro.dateLabel + '</td>' +
            '<td>' + fmt(ro.ndx) + '</td>' +
            '<td>' + fmt(ro.gold) + '</td>' +
            '<td>' + (ro.sox ? fmt(ro.sox) : '\u2014') + '</td>' +
            '<td>' + ro.ratio.toFixed(2) + '</td>' +
            '<td>' + nsStr + '</td>' +
            '<td>' + ro.s3dir + '</td>' +
            '<td>' + fmt(ro.s3Total) + '</td>' +
            '<td>' + ro.s4dir + '</td>' +
            '<td>' + fmt(ro.s4ndx * ro.ndx) + '</td>' +
            '<td>' + fmt(ro.s4gold * ro.gold) + '</td>' +
            '<td>' + (ro.sox ? fmt(ro.s4sox * ro.sox) : '\u2014') + '</td>' +
            '<td>' + fmt(ro.s4Total) + '</td>' +
            '<td>' + fmt(ro.dcaValue) + '</td>' +
            '<td class="' + dc3 + '">' + fmtDiff(ro.s3Total - ro.dcaValue) + '</td>' +
            '<td class="' + dc4 + '">' + fmtDiff(ro.s4Total - ro.dcaValue) + '</td>' +
            '</tr>';
    }
    tbody.innerHTML = html;
    drawChart(rows, monthlyAmt);
}

function drawChart(rows, monthlyAmt) {
    var ctx = document.getElementById("ratioChart").getContext("2d");
    if (chartInstance) chartInstance.destroy();
    var labels = rows.map(function(r){return r.dateLabel;});

    chartInstance = new Chart(ctx, {
        type: "bar",
        data: { labels: labels, datasets: [
            { label: "NDX/Gold", data: rows.map(function(r){return r.ratio;}), backgroundColor: rows.map(function(r){ return r.ratio>=9?"rgba(220,53,69,0.9)":r.ratio>=7?"rgba(255,127,14,0.8)":r.ratio>=4?"rgba(255,193,7,0.7)":r.ratio>=2.5?"rgba(40,167,69,0.6)":"rgba(40,167,69,1)";}), borderWidth: 0, yAxisID: "y" },
            { label: "S3 (NDX+Gold)", data: rows.map(function(r){return r.s3Total;}), type: "line", borderColor: "rgba(40,167,69,0.9)", borderWidth: 2, pointRadius: 0, yAxisID: "y1" },
            { label: "S4 (NDX+Gold+SOX)", data: rows.map(function(r){return r.s4Total;}), type: "line", borderColor: "rgba(156,39,176,0.9)", borderWidth: 2, pointRadius: 0, yAxisID: "y1" },
            { label: "DCA NDX", data: rows.map(function(r){return r.dcaValue;}), type: "line", borderColor: "rgba(30,60,150,0.7)", borderWidth: 2, pointRadius: 0, yAxisID: "y1", borderDash: [5,3] }
        ]},
        options: {
            responsive: true, maintainAspectRatio: false,
            interaction: { mode: "index", intersect: false },
            plugins: {
                legend: { display: true, position: "top" },
                title: { display: true, text: "NDX/Gold Ratio + All Strategies", font: { size: 14 } },
                tooltip: {
                    backgroundColor: "rgba(255,255,255,0.95)", titleColor: "#333", bodyColor: "#555",
                    borderColor: "#ddd", borderWidth: 1, padding: 12, displayColors: true,
                    callbacks: {
                        title: function(items) { return items[0].label; },
                        afterBody: function(items) {
                            var idx = items[0].dataIndex; var ro = rows[idx];
                            return ["\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500",
                                "S3 Action: " + ro.s3dir,
                                "S4 Action: " + ro.s4dir,
                                "NDX/SOX: " + (ro.ndxSoxRatio ? ro.ndxSoxRatio.toFixed(2) : "N/A")];
                        }
                    }
                }
            },
            scales: {
                x: { ticks: { maxTicksLimit: 20, font: { size: 10 } } },
                y: { position: "left", title: { display: true, text: "NDX/Gold Ratio" } },
                y1: { position: "right", title: { display: true, text: "Portfolio ($)" }, grid: { drawOnChartArea: false }, ticks: { callback: function(v) { return "$" + (v/1000000).toFixed(1) + "M"; } } }
            }
        }
    });
}

recalculate();
"""

js_code = js_code.replace("__DATA_PLACEHOLDER__", data_json)

html_template = """<!DOCTYPE html>
<html><head>
<title>NDX/Gold/SOX Rotation Strategy</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 20px; background: #f8f9fa; }
h1 { color: #333; margin-bottom: 10px; }
.controls { background: white; padding: 15px; border-radius: 8px; margin-bottom: 15px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); display: flex; align-items: center; gap: 15px; flex-wrap: wrap; }
.controls label { font-size: 13px; font-weight: bold; }
.controls input { padding: 5px 8px; border: 1px solid #ddd; border-radius: 4px; font-size: 13px; }
.summary { background: white; padding: 15px; border-radius: 8px; margin-bottom: 15px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
.summary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }
.summary-card { padding: 10px; border-radius: 6px; background: #f8f9fa; }
.summary-card .label { font-size: 10px; color: #666; text-transform: uppercase; }
.summary-card .value { font-size: 18px; font-weight: bold; margin-top: 3px; }
.s1 { border-left: 3px solid #1f77b4; }
.s3 { border-left: 3px solid #2ca02c; }
.s4 { border-left: 3px solid #9c27b0; }
#chartContainer { background: white; border-radius: 8px; padding: 15px; margin-bottom: 15px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); height: 350px; }
table { border-collapse: collapse; width: 100%; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1); font-size: 11px; }
th { background: #343a40; color: white; padding: 7px 4px; text-align: right; position: sticky; top: 0; z-index: 10; white-space: nowrap; }
td { padding: 5px 4px; border-bottom: 1px solid #eee; text-align: right; white-space: nowrap; }
tr:hover { background: #e9ecef !important; }
.pos { color: #28a745; font-weight: bold; }
.neg { color: #dc3545; font-weight: bold; }
</style>
</head><body>
<h1>NDX / Gold / SOX Rotation Strategy</h1>
<div class="controls">
<div><label>Start:</label> <input type="month" id="startDate" value="1994-06"></div>
<div><label>End:</label> <input type="month" id="endDate" value="2026-06"></div>
<div><label>Initial ($):</label> <input type="number" id="initialAmt" value="0" min="0" step="10000" style="width:90px;"></div>
<div><label>Monthly ($):</label> <input type="number" id="monthlyAmt" value="1000" min="0" step="100" style="width:80px;"></div>
<div style="display:flex;align-items:center;gap:6px;">
<label>Init NDX%:</label>
<input type="range" id="ndxPctSlider" min="0" max="100" value="50" style="width:100px;" oninput="document.getElementById('ndxPctLabel').textContent=this.value+'%NDX/'+(100-this.value)+'%Gold'">
<span id="ndxPctLabel" style="font-size:11px;">50%NDX/50%Gold</span>
</div>
<div><button onclick="recalculate()" style="padding:7px 16px;background:#343a40;color:white;border:none;border-radius:4px;cursor:pointer;">Apply</button></div>
</div>
<div class="summary" id="summary"></div>
<div id="chartContainer"><canvas id="ratioChart"></canvas></div>
<table><thead><tr>
<th>Date</th><th>NDX</th><th>Gold</th><th>SOX</th><th>NDX/Gold</th><th>NDX/SOX</th>
<th>S3 Action</th><th>S3 Total</th>
<th>S4 Action</th><th>S4 NDX</th><th>S4 Gold</th><th>S4 SOX</th><th>S4 Total</th>
<th>DCA</th><th>S3 vs DCA</th><th>S4 vs DCA</th>
</tr></thead><tbody id="tbody"></tbody></table>
<script>
__JS_PLACEHOLDER__
</script>
</body></html>"""

html = html_template.replace("__JS_PLACEHOLDER__", js_code)

output_path = "/Users/ajhanwa/workspace/stocks/ndx_gold_strategy.html"
with open(output_path, "w") as f:
    f.write(html)

print(f"Saved to: {output_path}")
print(f"Data points: {len(data)}")
