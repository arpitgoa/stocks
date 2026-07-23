"""
Backtest Engine Module
=======================
The core monthly rebalance loop with:
  - Gold rotation signal
  - VIX-adaptive lookback
  - Buffer-based stock selection
  - Leveraged ETF return tracking
  - CSV output generation
"""

import numpy as np
import pandas as pd
from pathlib import Path

from .paths import OUTPUT_DIR
from .data_loader import load_prices_for_universe, build_membership_lookup
from .momentum import calculate_momentum_scores, score_with_custom_lookback, _get_precomputed_by_date
from .metrics import xirr, max_drawdown


def run_backtest(universe_name, top_n=None, entry_rank=None, exit_rank=None,
                 ndx_gold_threshold=None, start_year=None):
    """
    Run the momentum backtest for a given universe.
    
    Args:
        universe_name: Key from UNIVERSE_CONFIGS
        top_n: Number of stocks to hold (overrides config)
        entry_rank: Max rank for new entry (overrides config)
        exit_rank: Max rank before forced exit (overrides config)
        ndx_gold_threshold: Gold rotation threshold (overrides config)
        start_year: Backtest start year (overrides config)
        
    Returns:
        Tuple of (final_portfolio_value, holdings_history_list)
    """
    # Import here to avoid circular dependency
    from universe_config import get_config
    from leveraged_config import LEVERAGED_ETF_MAP

    config = get_config(universe_name)
    universe_folder = config["folder"]

    if top_n is None:            top_n = config["top_n"]
    if entry_rank is None:       entry_rank = config["entry_rank"]
    if exit_rank is None:        exit_rank = config["exit_rank"]
    if ndx_gold_threshold is None: ndx_gold_threshold = config["gold_threshold"]
    if start_year is None:       start_year = config["start_year"]

    benchmark_symbol = config["benchmark"]
    benchmark_etf = config.get("benchmark_etf", None)
    gold_signal_index = config.get("gold_signal_index", "$NDX")

    # Load data
    lev_tickers = set(LEVERAGED_ETF_MAP.values())
    prices = load_prices_for_universe(universe_folder, config, lev_tickers)

    if benchmark_symbol not in prices.columns and benchmark_etf and benchmark_etf in prices.columns:
        benchmark_symbol = benchmark_etf

    print(f"\n{'='*70}")
    print(f"BACKTEST: {universe_name.upper()} Momentum Top {top_n}")
    print(f"Buffer: entry ≤ {entry_rank}, exit > {exit_rank}")
    print(f"Gold rotation: {gold_signal_index}/XAUUSD ≥ {ndx_gold_threshold}")
    print(f"Start year: {start_year}")
    print(f"Benchmark: {benchmark_symbol}")
    print(f"{'='*70}")

    # Generate monthly rebalance dates (last trading day of each month)
    rebal_dates = _generate_rebalance_dates(prices, start_year)
    print(f"Rebalance dates: {len(rebal_dates)} ({rebal_dates[0].date()} to {rebal_dates[-1].date()})")

    # Pre-build membership lookup for all rebalance dates
    print("  Pre-building membership lookup...")
    membership_lookup = build_membership_lookup(universe_folder, rebal_dates)

    # Warm up precomputed scores cache
    _get_precomputed_by_date()

    # Build integer index map for fast price slicing
    date_to_idx = {d: prices.index.searchsorted(d) for d in rebal_dates}

    # Run the main loop
    holdings_history = _run_monthly_loop(
        prices=prices,
        rebal_dates=rebal_dates,
        date_to_idx=date_to_idx,
        membership_lookup=membership_lookup,
        config=config,
        top_n=top_n,
        entry_rank=entry_rank,
        exit_rank=exit_rank,
        ndx_gold_threshold=ndx_gold_threshold,
        gold_signal_index=gold_signal_index,
        leveraged_map=LEVERAGED_ETF_MAP,
    )

    # Calculate summary metrics
    portfolio_value = holdings_history[-1]["Portfolio_Value"]
    total_invested = 100000 + len(holdings_history) * 1000
    years = (holdings_history[-1]["Next_Rebal"] - holdings_history[0]["Rebal_Date"]).days / 365.25
    multiple = portfolio_value / total_invested

    cashflows = [(holdings_history[0]["Rebal_Date"], -100000)]
    for h in holdings_history:
        cashflows.append((h["Rebal_Date"], -1000))
    cashflows.append((holdings_history[-1]["Next_Rebal"], portfolio_value))
    xirr_rate = xirr(cashflows)

    port_values = [100000] + [h["Portfolio_Value"] for h in holdings_history]
    mdd, _, _ = max_drawdown(port_values)

    print(f"\n{'='*70}")
    print(f"RESULTS: {universe_name.upper()} Momentum Top {top_n}")
    print(f"  Period: {holdings_history[0]['Rebal_Date'].date()} to {holdings_history[-1]['Next_Rebal'].date()} ({years:.1f} years)")
    print(f"  Total invested: ${total_invested:,.0f}")
    print(f"  Ending value:   ${portfolio_value:,.0f}")
    print(f"  Multiple:       {multiple:.1f}x")
    print(f"  XIRR:           {xirr_rate:.1%}")
    print(f"  Max Drawdown:   -{mdd:.1%}")
    print(f"{'='*70}")

    # Save output CSV
    _save_wide_csv(universe_name, holdings_history, prices, benchmark_symbol, config)

    return portfolio_value, holdings_history


# ============================================================
# INTERNAL HELPERS
# ============================================================

def _generate_rebalance_dates(prices, start_year):
    """Generate list of monthly rebalance dates (last trading day of each month)."""
    rebal_dates = []
    last_date = prices.index[-1]
    for year in range(start_year, last_date.year + 1):
        for month in range(1, 13):
            try:
                month_data = prices.loc[f"{year}-{month:02d}"]
                if len(month_data) > 0:
                    rebal_dates.append(month_data.index[-1])
            except KeyError:
                continue
    rebal_dates = [d for d in rebal_dates if d < last_date - pd.Timedelta(days=5)]
    return rebal_dates


def _run_monthly_loop(prices, rebal_dates, date_to_idx, membership_lookup,
                      config, top_n, entry_rank, exit_rank,
                      ndx_gold_threshold, gold_signal_index, leveraged_map):
    """The main monthly rebalance loop."""
    
    portfolio_value = 100000.0
    monthly_contribution = 1000.0
    total_invested = 100000.0
    holdings_history = []
    current_holdings = set()
    total_trades = 0

    # Pre-compute 10-month MA for position sizing (informational only — not applied to returns)
    ndx_col = gold_signal_index if gold_signal_index in prices.columns else "$NDX"
    _ndx_monthly = prices[ndx_col].dropna().resample("ME").last() if ndx_col in prices.columns else pd.Series(dtype=float)
    _ndx_10mma = _ndx_monthly.rolling(10).mean() if len(_ndx_monthly) >= 10 else pd.Series(dtype=float)

    for i, rebal_date in enumerate(rebal_dates):
        next_rebal = rebal_dates[i + 1] if i + 1 < len(rebal_dates) else prices.index[-1]
        cutoff_idx = date_to_idx[rebal_date]

        # --- Gold Rotation Check ---
        gold_triggered = _check_gold_rotation(
            prices, cutoff_idx, gold_signal_index, ndx_gold_threshold
        )
        if gold_triggered:
            next_idx = prices.index.searchsorted(next_rebal)
            hold_period = prices["XAUUSD"].iloc[cutoff_idx:next_idx + 1].dropna()
            gold_ret = (hold_period.iloc[-1] / hold_period.iloc[0] - 1) if len(hold_period) >= 2 else 0
            portfolio_value *= (1 + gold_ret)
            portfolio_value += monthly_contribution
            total_invested += monthly_contribution

            ratio = prices[gold_signal_index].iloc[:cutoff_idx + 1].dropna().iloc[-1] / \
                    prices["XAUUSD"].iloc[:cutoff_idx + 1].dropna().iloc[-1]

            holdings_history.append({
                "Rebal_Date": rebal_date,
                "Next_Rebal": next_rebal,
                "Period_Return": gold_ret,
                "Leveraged_Return": gold_ret,
                "Portfolio_Value": portfolio_value,
                "Holdings": [{"Ticker": "XAUUSD", "Weight": 1.0}],
                "Ticker_Returns": {"XAUUSD": round(gold_ret * 100, 2)},
                "Lev_Ticker_Returns": {"XAUUSD": round(gold_ret * 100, 2)},
                "Trades": 0,
                "Top10": [f"GOLD ({gold_signal_index}/XAUUSD={ratio:.2f})"],
                "Removed": [],
                "Added": ["XAUUSD"],
            })
            current_holdings = set()
            continue

        # --- Momentum Scoring ---
        universe = membership_lookup[rebal_date]

        # VIX-adaptive lookback
        vix_threshold = config.get("vix_threshold", None)
        custom_lookback = None
        if vix_threshold and "$VIX" in prices.columns:
            vix_ts = prices["$VIX"].loc[:rebal_date].dropna()
            if len(vix_ts) > 0 and vix_ts.iloc[-1] > vix_threshold:
                custom_lookback = (config.get("vix_fast_long", 126), config.get("vix_fast_short", 42))

        if custom_lookback:
            # VIX fast mode — use vix_momentum_blend if specified
            vix_blend = config.get("vix_momentum_blend", (0.5, 0.5))
            scores = score_with_custom_lookback(
                prices, universe, rebal_date, custom_lookback[0], custom_lookback[1],
                weight_12=vix_blend[0], weight_6=vix_blend[1]
            )
        else:
            raw_return = config.get("raw_return", False)
            # Get per-universe momentum blend (default 70/30)
            blend = config.get("momentum_blend", (0.7, 0.3))
            # Custom base lookback (default 252/126)
            base_long = config.get("lookback_long", 252)
            base_short = config.get("lookback_short", 126)
            if base_long != 252 or base_short != 126:
                # Non-standard lookback — compute live
                scores = score_with_custom_lookback(
                    prices, universe, rebal_date, base_long, base_short,
                    weight_12=blend[0], weight_6=blend[1]
                )
            else:
                scores = calculate_momentum_scores(prices, universe, cutoff_idx,
                                                   raw_return=raw_return,
                                                   weight_12=blend[0], weight_6=blend[1])

        if scores.empty:
            portfolio_value += monthly_contribution
            total_invested += monthly_contribution
            continue

        # --- Buffer Selection Logic ---
        scores["Rank"] = range(1, len(scores) + 1)
        ranked = dict(zip(scores["Ticker"], scores["Rank"]))
        new_portfolio = _apply_buffer_logic(
            current_holdings, ranked, scores, top_n, entry_rank, exit_rank
        )

        trades = len(new_portfolio - current_holdings) + len(current_holdings - new_portfolio)
        added = sorted(new_portfolio - current_holdings)
        removed = sorted(current_holdings - new_portfolio)
        total_trades += trades
        current_holdings = new_portfolio

        # --- Calculate Period Returns ---
        weight = 1.0 / len(new_portfolio) if new_portfolio else 0
        next_idx = prices.index.searchsorted(next_rebal)
        hold_slice = prices.iloc[cutoff_idx:next_idx + 1]

        if len(hold_slice) < 2:
            portfolio_value += monthly_contribution
            total_invested += monthly_contribution
            continue

        period_ret, ticker_returns, lev_ticker_returns = _calculate_period_returns(
            hold_slice, new_portfolio, weight, leveraged_map
        )

        lev_period_ret = (
            sum(lev_ticker_returns.values()) / len(new_portfolio) / 100
            if lev_ticker_returns else 0
        )

        # --- 10-Month Moving Average (informational — stored but not applied) ---
        mma_scale = 1.0  # Always 1x in backtest; MMA is advisory signal only

        portfolio_value *= (1 + period_ret)
        portfolio_value += monthly_contribution
        total_invested += monthly_contribution

        # VIX value for this month
        vix_val = None
        if "$VIX" in prices.columns:
            vix_ts = prices["$VIX"].loc[:rebal_date].dropna()
            if len(vix_ts) > 0:
                vix_val = round(vix_ts.iloc[-1], 1)

        holdings_history.append({
            "Rebal_Date": rebal_date,
            "Next_Rebal": next_rebal,
            "Period_Return": period_ret,
            "Leveraged_Return": lev_period_ret,
            "Portfolio_Value": portfolio_value,
            "Holdings": [{"Ticker": t, "Weight": weight} for t in sorted(new_portfolio)],
            "Ticker_Returns": ticker_returns,
            "Lev_Ticker_Returns": lev_ticker_returns,
            "Trades": trades,
            "Top10": scores.head(10)["Ticker"].tolist(),
            "Removed": removed,
            "Added": added,
            "VIX": vix_val,
            "VIX_Fast": custom_lookback is not None if config.get("vix_threshold") else False,
            "MMA_Scale": mma_scale,
        })

        if i % 50 == 0:
            print(f"  {rebal_date.date()}: Val=${portfolio_value:,.0f} | Held: {sorted(new_portfolio)}")

    print(f"\n  Total trades: {total_trades}")
    print(f"  Total invested: ${total_invested:,.0f}")
    return holdings_history


def _check_gold_rotation(prices, cutoff_idx, gold_signal_index, threshold):
    """Check if gold rotation signal is triggered."""
    if not threshold:
        return False
    if gold_signal_index not in prices.columns or "XAUUSD" not in prices.columns:
        return False
    idx_p = prices[gold_signal_index].iloc[:cutoff_idx + 1].dropna()
    xau_p = prices["XAUUSD"].iloc[:cutoff_idx + 1].dropna()
    if len(idx_p) == 0 or len(xau_p) == 0:
        return False
    ratio = idx_p.iloc[-1] / xau_p.iloc[-1]
    return ratio >= threshold


def _apply_buffer_logic(current_holdings, ranked, scores, top_n, entry_rank, exit_rank):
    """Apply the buffer-based stock selection logic."""
    # Retain existing holdings that haven't fallen below exit rank
    retained = {t for t in current_holdings if t in ranked and ranked[t] <= exit_rank}
    new_portfolio = retained.copy()
    
    # Fill remaining slots from top-ranked stocks within entry rank
    for _, row in scores.iterrows():
        if len(new_portfolio) >= top_n:
            break
        if row["Ticker"] not in new_portfolio and row["Rank"] <= entry_rank:
            new_portfolio.add(row["Ticker"])
    
    # If still not full, fill from best available regardless of entry rank
    if len(new_portfolio) < top_n:
        for _, row in scores.iterrows():
            if len(new_portfolio) >= top_n:
                break
            if row["Ticker"] not in new_portfolio:
                new_portfolio.add(row["Ticker"])
    
    return new_portfolio


def _calculate_period_returns(hold_slice, portfolio, weight, leveraged_map):
    """Calculate regular and leveraged returns for the holding period."""
    period_ret = 0
    ticker_returns = {}
    lev_ticker_returns = {}
    
    held_tickers = [t for t in portfolio if t in hold_slice.columns]
    for t in held_tickers:
        tp = hold_slice[t].dropna()
        if len(tp) < 2:
            continue
        ticker_ret = tp.iloc[-1] / tp.iloc[0] - 1
        period_ret += weight * ticker_ret
        ticker_returns[t] = round(ticker_ret * 100, 2)

        # Check for leveraged ETF
        lev = leveraged_map.get(t)
        if lev and lev in hold_slice.columns:
            lp = hold_slice[lev].dropna()
            if len(lp) >= 2:
                lev_ticker_returns[t] = round((lp.iloc[-1] / lp.iloc[0] - 1) * 100, 2)
                continue
        lev_ticker_returns[t] = ticker_returns[t]
    
    return period_ret, ticker_returns, lev_ticker_returns


def _save_wide_csv(universe_name, holdings_history, prices, benchmark_symbol, config):
    """Save the backtest results as a wide-format CSV for dashboard consumption."""
    benchmark_etf = config.get("benchmark_etf", None)
    rows = []
    
    for h in holdings_history:
        rebal_date = h["Rebal_Date"]
        next_rebal = h["Next_Rebal"]
        port_start = (
            h["Portfolio_Value"] / (1 + h["Period_Return"])
            if h["Period_Return"] != -1 else h["Portfolio_Value"]
        )

        row = {
            "Start_Date": rebal_date.strftime("%Y-%m-%d"),
            "End_Date": next_rebal.strftime("%Y-%m-%d"),
            "Portfolio_Start": round(port_start, 2),
            "Portfolio_End": round(h["Portfolio_Value"], 2),
            "Portfolio_Return_Pct": round(h["Period_Return"] * 100, 2),
            "Leveraged_Return_Pct": round(h.get("Leveraged_Return", h["Period_Return"]) * 100, 2),
            "VIX": h.get("VIX", ""),
            "VIX_Fast": h.get("VIX_Fast", False),
        }

        # Benchmark return
        bench_ret = _get_benchmark_return(prices, rebal_date, next_rebal, benchmark_symbol, benchmark_etf)
        row["Benchmark_Return_Pct"] = round(bench_ret * 100, 2) if bench_ret is not None else ""

        # Top 10 and changes
        row["Top10"] = ", ".join(h.get("Top10", []))
        added = h.get("Added", [])
        removed = h.get("Removed", [])
        if added and removed:
            row["Changes"] = ", ".join([f"{r}→{a}" for r, a in zip(removed, added)])
        elif added:
            row["Changes"] = "+" + ", +".join(added)
        else:
            row["Changes"] = ""

        # Per-ticker columns
        ticker_returns = h.get("Ticker_Returns", {})
        lev_ticker_returns = h.get("Lev_Ticker_Returns", {})
        for holding in h["Holdings"]:
            ticker = holding["Ticker"]
            wt = holding["Weight"]
            if ticker in ticker_returns:
                row[f"{ticker}_Pct"] = round(wt * 100, 2)
                row[f"{ticker}_Ret"] = ticker_returns[ticker]
                row[f"{ticker}_LevRet"] = lev_ticker_returns.get(ticker, ticker_returns[ticker])

        rows.append(row)

    dashboard_dir = OUTPUT_DIR / "dashboards" / universe_name
    dashboard_dir.mkdir(parents=True, exist_ok=True)
    output_file = dashboard_dir / "backtest_wide.csv"
    pd.DataFrame(rows).to_csv(output_file, index=False)
    print(f"  Saved: {output_file}")


def _get_benchmark_return(prices, start_date, end_date, benchmark_symbol, benchmark_etf):
    """Get benchmark return for a period, trying primary then ETF."""
    if benchmark_symbol in prices.columns:
        bp = prices.loc[start_date:end_date, benchmark_symbol].dropna()
        if len(bp) >= 2:
            return bp.iloc[-1] / bp.iloc[0] - 1
    if benchmark_etf and benchmark_etf in prices.columns:
        bp = prices.loc[start_date:end_date, benchmark_etf].dropna()
        if len(bp) >= 2:
            return bp.iloc[-1] / bp.iloc[0] - 1
    return None
