"""Run one scan cycle with DEBUG logging — no infinite loop."""
from __future__ import annotations

import logging
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)

from scanner.config import settings
from scanner.data.cache import CandleCache
from scanner.data.fetcher import TwelveDataFetcher
from scanner.main import run_scan
from scanner.state.tracker import AlertTracker

fetcher = TwelveDataFetcher(api_key=settings.TWELVE_DATA_API_KEY)
cache = CandleCache(fetcher)
tracker = AlertTracker()

run_scan(cache, tracker)

print("Dry-run completado.")
