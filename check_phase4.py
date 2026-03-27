"""
Smoke-test for Phase 4: M15 entry model detection inside H4 CRT zones.
Run: python check_phase4.py
"""
import asyncio
import logging
import sys

sys.stdout.reconfigure(encoding="utf-8")

from config import settings
from data.twelvedata_client import TwelveDataClient
from data.candle_store import CandleStore
from core.crt_detector import detect
from core.htf_confluence import run_confluence
from core.entry_models import find_entry
from core.models import Score

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")


async def main() -> None:
    store = CandleStore(buffer_size=settings.candle_buffer_size)

    async with TwelveDataClient(settings) as client:
        print("Fetching D + H4 + M15 candles for all pairs...\n")
        for i, pair in enumerate(settings.pairs):
            if i > 0:
                await asyncio.sleep(8)
            for gran in ("D", "H4", "M15"):
                candles = await client.get_candles(pair, gran, count=100)
                store.update(candles)
                await asyncio.sleep(8)
            print(f"  {pair} done")

    total_entries = 0

    for pair in settings.pairs:
        h4_signals = detect(store.get(pair, "H4"), pair, "H4")
        recent = h4_signals[-5:]
        results = run_confluence(recent, store, pair)

        score_a = [r for r in results if r.score == Score.A]
        m15_df = store.get(pair, "M15")

        for conf in score_a:
            entry = find_entry(conf, m15_df)
            if entry:
                total_entries += 1
                print(f"\n{pair} — Score A + M15 Entry:")
                print(f"  CRT : {conf.signal!r}")
                print(f"  KL  : {conf.key_level!r}")
                print(f"  Entry: {entry!r}")

    print(f"\nTotal M15 entries found: {total_entries}")
    print("Phase 4 OK ✓")


if __name__ == "__main__":
    asyncio.run(main())
