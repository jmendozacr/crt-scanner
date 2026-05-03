"""Run one scan cycle with DEBUG logging — no infinite loop."""
from __future__ import annotations

import argparse
import logging
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from scanner.config import settings
from scanner.config.pairs import PAIRS, SYMBOLS, Pair
from scanner.data.cache import CandleCache
from scanner.data.fetcher import TwelveDataFetcher
from scanner.main import run_scan
from scanner.state.tracker import AlertTracker


def main() -> None:
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )

    parser = argparse.ArgumentParser(description="CRT Scanner — dry run")
    parser.add_argument(
        "--pair",
        metavar="SYMBOL",
        default=None,
        help="Scan only this pair (default: all pairs)",
    )
    args = parser.parse_args()

    selected_pairs: list[Pair] | None = None
    if args.pair is not None:
        normalized = args.pair.strip().upper()
        if normalized not in SYMBOLS:
            print(
                f"Error: '{args.pair}' is not a valid pair. "
                f"Valid pairs: {', '.join(SYMBOLS)}",
                file=sys.stderr,
            )
            sys.exit(1)
        selected_pairs = [p for p in PAIRS if p.symbol == normalized]

    fetcher = TwelveDataFetcher(api_key=settings.TWELVE_DATA_API_KEY)
    cache = CandleCache(fetcher)
    tracker = AlertTracker()

    run_scan(cache, tracker, selected_pairs)

    print("Dry-run completado.")


if __name__ == "__main__":
    main()
