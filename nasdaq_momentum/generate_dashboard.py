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
from universe_config import get_config, UNIVERSE_CONFIGS

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
        lev_returns = {}
        for col in df.columns:
            if col.endswith("_Ret") and not col.endswith("_LevRet") and row[col] != "" and pd.notna(row[col]):
                ticker = col.replace("_Ret", "")
                returns[ticker] = float(row[col])
            if col.endswith("_LevRet") and row[col] != "" and pd.notna(row[col]):
                ticker = col.replace("_LevRet", "")
                lev_returns[ticker] = float(row[col])

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
            "levRet": float(row["Leveraged_Return_Pct"]) if "Leveraged_Return_Pct" in row and row.get("Leveraged_Return_Pct", "") != "" and pd.notna(row.get("Leveraged_Return_Pct")) else None,
            "qqqRet": float(row["Benchmark_Return_Pct"]) if row["Benchmark_Return_Pct"] != "" and pd.notna(row["Benchmark_Return_Pct"]) else None,
            "holdings": holdings,
            "returns": returns,
            "levReturns": lev_returns,
            "benchReturns": bench_returns,
            "top7": row.get("Top10", ""),
            "changes": row.get("Changes", ""),
            "vix": float(row["VIX"]) if "VIX" in row and row.get("VIX", "") != "" and pd.notna(row.get("VIX")) else None,
            "vixFast": bool(row.get("VIX_Fast", False)) if "VIX_Fast" in row else False,
        })

    # Determine start date for the input
    start_month = data[0]["start"][:7]

    html_content = _build_html(data, label, start_month, config=get_config(universe_name))

    output_file = dashboard_dir / "dashboard.html"
    with open(output_file, "w") as f:
        f.write(html_content)

    print(f"Generated: {output_file}")
    print(f"  Data points: {len(data)} months")


from dashboard_template import TEMPLATE_BEFORE, TEMPLATE_AFTER


def _build_html(data, label, start_month, config=None):
    """Build HTML dashboard using the full-featured template."""
    data_json = json.dumps(data)
    
    # Build subtitle from config
    if config:
        top_n = config.get("top_n", 3)
        entry = config.get("entry_rank", 3)
        exit_r = config.get("exit_rank", 7)
        gold_idx = config.get("gold_signal_index", "$NDX")
        gold_thresh = config.get("gold_threshold", 7.0)
        benchmark = config.get("benchmark", "$NDX")
        subtitle = f"Monthly rebalance · Top {top_n} · Buffer {entry}/{exit_r} · Equal weight · Gold when {gold_idx}/XAUUSD ≥ {gold_thresh}"
        benchmark_label = benchmark
    else:
        subtitle = "Monthly rebalance · Buffer 3/7 · Equal weight"
        benchmark_label = "Benchmark"
    
    tpl_before = (TEMPLATE_BEFORE
        .replace("{{TITLE}}", label)
        .replace("{{LABEL}}", label)
        .replace("{{START_MONTH}}", start_month)
        .replace("{{SUBTITLE}}", subtitle)
        .replace("{{BENCHMARK_LABEL}}", benchmark_label)
        .replace("{{UNIVERSE_LABEL}}", label)
    )
    
    tpl_after = TEMPLATE_AFTER.replace("{{BENCHMARK_LABEL}}", benchmark_label)
    
    return tpl_before + data_json + tpl_after


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
