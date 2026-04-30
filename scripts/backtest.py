from __future__ import annotations

import sys
from pathlib import Path

# When run as a script (python scripts/backtest.py), Python adds scripts/ to
# sys.path instead of the project root. Fix it before any other imports.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import argparse

from scripts.backtest_data import fetch_and_cache, load_candles
from scripts.backtest_engine import FunnelCounts, TradeRecord, walk_pair
from scripts.backtest_report import aggregate, print_report, save_csv

_TIMEFRAMES = ["1day", "4h", "15min"]


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="CRT Strategy Walk-Forward Backtest")
    p.add_argument(
        "--pairs", nargs="+", metavar="SYMBOL", help="Symbols to backtest (default: all)"
    )
    p.add_argument("--outputsize", type=int, default=2000)
    p.add_argument("--csv", metavar="PATH", help="Save trades to CSV")
    p.add_argument("--no-fetch", action="store_true", help="Use cached data only")
    p.add_argument("--min-history", type=int, default=200)
    p.add_argument("--lookahead", type=int, default=20)
    return p


def main() -> None:
    args = _build_parser().parse_args()

    from scanner.config.pairs import SYMBOLS

    symbols = args.pairs if args.pairs else SYMBOLS

    fetcher = None
    if not args.no_fetch:
        from scanner.config import settings
        from scanner.data.fetcher import TwelveDataFetcher

        fetcher = TwelveDataFetcher(api_key=settings.TWELVE_DATA_API_KEY)

    all_trades: list[TradeRecord] = []
    all_funnels: list[FunnelCounts] = []

    for symbol in symbols:
        try:
            candles_by_tf: dict = {}
            for tf in _TIMEFRAMES:
                fetch_and_cache(symbol, tf, args.outputsize, fetcher, no_fetch=args.no_fetch)
                candles_by_tf[tf] = load_candles(symbol, tf)
        except FileNotFoundError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(2)
        except Exception as e:
            print(f"ERROR fetching {symbol}: {e}", file=sys.stderr)
            sys.exit(1)

        trades, funnel = walk_pair(
            symbol,
            daily=candles_by_tf["1day"],
            h4=candles_by_tf["4h"],
            m15=candles_by_tf["15min"],
            min_history=args.min_history,
            lookahead=args.lookahead,
        )
        all_trades.extend(trades)
        all_funnels.append(funnel)

    stats = aggregate(all_trades)
    print_report(all_trades, stats, all_funnels)

    if args.csv:
        save_csv(all_trades, args.csv)
        print(f"\nSaved to: {args.csv}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(0)
