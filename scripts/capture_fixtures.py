"""Fetch live candle data and save as JSON fixtures for offline testing."""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys

from dotenv import load_dotenv

load_dotenv()

from scanner.data.fetcher import TwelveDataFetcher

PAIRS = [
    "EUR/USD",
    "GBP/USD",
    "USD/CAD",
]

TIMEFRAMES = ["1day", "2day", "3day", "4h", "15min"]

FIXTURES_DIR = pathlib.Path(__file__).parent.parent / "tests" / "fixtures"


def normalize_filename(symbol: str, timeframe: str) -> str:
    return f"{symbol.replace('/', '_')}_{timeframe}.json"


def fetch_and_save(symbol: str, timeframe: str, force: bool) -> None:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    filename = normalize_filename(symbol, timeframe)
    path = FIXTURES_DIR / filename

    if path.exists() and not force:
        print(f"  skip  {filename} (already exists, use --force to overwrite)")
        return

    api_key = os.environ["TWELVE_DATA_API_KEY"]
    fetcher = TwelveDataFetcher(api_key=api_key)
    candles = fetcher.fetch(symbol, timeframe)

    rows = [
        {
            "datetime": c.datetime,
            "open": str(c.open),
            "high": str(c.high),
            "low": str(c.low),
            "close": str(c.close),
            "volume": str(c.volume),
        }
        for c in candles
    ]

    path.write_text(json.dumps(rows, indent=2))
    print(f"  saved {filename} ({len(rows)} candles)")


def main(force: bool) -> None:
    had_error = False
    for symbol in PAIRS:
        for timeframe in TIMEFRAMES:
            print(f"Fetching {symbol} {timeframe}...")
            try:
                fetch_and_save(symbol, timeframe, force)
            except Exception as exc:
                print(f"  ERROR: {exc}")
                had_error = True
    if had_error:
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Capture fixture candle data from TwelveData API.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing fixture files.",
    )
    args = parser.parse_args()
    main(force=args.force)
