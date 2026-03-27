"""
Smoke-test for Phase 3: HTF confluence against live data.
Run: python check_phase3.py
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
from core.models import Score

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")


async def main() -> None:
    store = CandleStore(buffer_size=settings.candle_buffer_size)

    async with TwelveDataClient(settings) as client:
        print("Fetching D + H4 candles for all pairs...\n")
        for i, pair in enumerate(settings.pairs):
            if i > 0:
                await asyncio.sleep(8)
            for gran in ("D", "H4"):
                candles = await client.get_candles(pair, gran, count=100)
                store.update(candles)
                await asyncio.sleep(8)
            print(f"  {pair} done")

    score_a = score_b = 0

    for pair in settings.pairs:
        h4_signals = detect(store.get(pair, "H4"), pair, "H4")
        # Only check the 5 most recent H4 signals (avoid spam)
        recent = h4_signals[-5:]
        results = run_confluence(recent, store, pair)

        a = [r for r in results if r.score == Score.A]
        b = [r for r in results if r.score == Score.B]
        score_a += len(a)
        score_b += len(b)

        if a:
            print(f"\n{pair} — {len(a)} Score A signal(s):")
            for r in a:
                kl = r.key_level
                print(f"  {r.signal!r}")
                print(f"  └─ {kl!r}")

    print(f"\nScore A: {score_a}  |  Score B: {score_b}")
    print("Phase 3 OK ✓")


if __name__ == "__main__":
    asyncio.run(main())
