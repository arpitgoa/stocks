"""
Momentum Backtest Runner (CLI)
===============================
Thin CLI wrapper around core.engine.run_backtest().

Usage:
    python run_backtest.py --universe nasdaq100
    python run_backtest.py --universe sp500 --top-n 5 --exit-rank 10
    python run_backtest.py --all
    python run_backtest.py --all --dashboard
    python run_backtest.py --list
"""

import argparse
from universe_config import UNIVERSE_CONFIGS, list_universes
from core import run_backtest


def main():
    parser = argparse.ArgumentParser(description="Momentum Backtest Runner")
    parser.add_argument("--universe", type=str, help="Universe name to backtest")
    parser.add_argument("--all", action="store_true", help="Run all universes")
    parser.add_argument("--top-n", type=int, default=None, help="Override top N stocks")
    parser.add_argument("--entry-rank", type=int, default=None, help="Override entry rank")
    parser.add_argument("--exit-rank", type=int, default=None, help="Override exit rank")
    parser.add_argument("--gold-threshold", type=float, default=None, help="Override gold threshold")
    parser.add_argument("--start-year", type=int, default=None, help="Override start year")
    parser.add_argument("--list", action="store_true", help="List available universes")
    parser.add_argument("--dashboard", action="store_true", help="Generate dashboard after backtest")
    args = parser.parse_args()

    if args.list:
        list_universes()
        return

    if args.all:
        universes_to_run = list(UNIVERSE_CONFIGS.keys())
    elif args.universe:
        if args.universe not in UNIVERSE_CONFIGS:
            print(f"Unknown universe: {args.universe}. Use --list to see options.")
            return
        universes_to_run = [args.universe]
    else:
        print("Error: --universe or --all required. Use --list to see options.")
        return

    for universe_name in universes_to_run:
        try:
            run_backtest(
                universe_name=universe_name,
                top_n=args.top_n,
                entry_rank=args.entry_rank,
                exit_rank=args.exit_rank,
                ndx_gold_threshold=args.gold_threshold,
                start_year=args.start_year,
            )
            if args.dashboard:
                print("\nGenerating dashboard...")
                from generate_dashboard import generate_dashboard
                generate_dashboard(universe_name)
        except Exception as e:
            print(f"\nERROR running {universe_name}: {e}")
            import traceback
            traceback.print_exc()
            continue


if __name__ == "__main__":
    main()
