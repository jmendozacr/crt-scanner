"""
Smoke-test for Phase 2: runs CRT detector against live H4 data.
Run: python check_phase2.py
"""
import asyncio
import logging
import sys

sys.stdout.reconfigure(encoding="utf-8")  # Windows terminal UTF-8

from config import settings
from data.twelvedata_client import TwelveDataClient
from data.candle_store import CandleStore
from core.crt_detector import detect

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")


async def main() -> None:
    store = CandleStore(buffer_size=settings.candle_buffer_size)

    async with TwelveDataClient(settings) as client:
        print("Fetching last 100 H4 candles for all pairs...\n")
        for i, pair in enumerate(settings.pairs):
            if i > 0:
                await asyncio.sleep(8)  # free tier: 8 req/min
            candles = await client.get_candles(pair, "H4", count=100)
            store.update(candles)
            print(f"  {pair} — {len(candles)} candles fetched")

    total = 0
    for pair in settings.pairs:
        df = store.get(pair, "H4")
        signals = detect(df, pair, "H4")
        if signals:
            for s in signals[-3:]:  # show last 3 signals per pair
                print(s)
            total += len(signals)
        else:
            print(f"  {pair} H4 — no CRT signals in last 100 candles")

    print(f"\nTotal signals found: {total}")
    print("Phase 2 OK ✓")


if __name__ == "__main__":
    asyncio.run(main())
