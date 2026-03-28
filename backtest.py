"""
CRT Scanner — backtesting CLI.

Usage:
    python backtest.py                           # rr=2, all pairs, min_score from .env
    python backtest.py --rr 3                    # 3:1 RR
    python backtest.py --pair EUR_USD            # single pair
    python backtest.py --rr 3 --min-score B      # Score A+B signals
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys

sys.stdout.reconfigure(encoding="utf-8")

from config import MinScore, settings
from data.candle_store import CandleStore
from data.twelvedata_client import TwelveDataClient
from backtest.runner import bootstrap_backtest, run_backtest
from backtest.report import print_report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CRT Scanner — Backtest")
    parser.add_argument(
        "--rr", type=float, default=2.0,
        help="Reward-to-risk ratio for TP calculation (default: 2.0)",
    )
    parser.add_argument(
        "--pair", type=str, default=None,
        help="Single pair override, e.g. EUR_USD (default: all pairs from .env)",
    )
    parser.add_argument(
        "--min-score", type=str, choices=["A", "B"],
        default=settings.min_score.value,
        help="Minimum confluence score filter (default: from .env)",
    )
    parser.add_argument(
        "--lookback", type=int, default=10,
        help="H4 candles to scan for CRT ref (default: 10)",
    )
    return parser.parse_args()


async def main() -> None:
    args = _parse_args()

    if args.rr <= 0:
        print(f"Error: --rr must be positive, got {args.rr}")
        sys.exit(1)

    pairs = [args.pair] if args.pair else list(settings.pairs)
    min_score = MinScore(args.min_score)
    rr = args.rr

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )
    logger = logging.getLogger(__name__)
    logger.info(
        "Backtest starting — %d pair(s), RR 1:%g, min_score=%s, lookback=%d",
        len(pairs), rr, min_score.value, args.lookback,
    )

    # Use a larger buffer to hold full historical data
    store = CandleStore(buffer_size=5000)

    async with TwelveDataClient(settings) as client:
        await bootstrap_backtest(client, store, pairs)
        results = await run_backtest(store, pairs, min_score, rr, lookback=args.lookback)

    print_report(results, rr=rr, min_score_label=min_score.value, lookback=args.lookback)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBacktest stopped.")
