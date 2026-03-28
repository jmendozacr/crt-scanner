"""
End-to-end integration smoke test for Phase 6.
Bootstraps first pair only, runs the full pipeline, prints any found signals.
No Telegram messages are sent.

Run: python check_phase6.py
"""
import asyncio
import logging
import sys

sys.stdout.reconfigure(encoding="utf-8")

from config import settings
from data.twelvedata_client import TwelveDataClient
from data.candle_store import CandleStore
from main import _bootstrap, _process_pair

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


async def main() -> None:
    pair = settings.pairs[0]
    store = CandleStore(buffer_size=settings.candle_buffer_size)

    print(f"Bootstrapping {pair} (D + H4 + M15, 100 candles each)...\n")
    async with TwelveDataClient(settings) as client:
        await _bootstrap(client, store, [pair])

    print(f"\nRunning pipeline for {pair} (min_score={settings.min_score.value})...\n")
    entry = await _process_pair(pair, store, bot=None, min_score=settings.min_score)

    if entry:
        print("Entry signal found:")
        print(f"  Model     : {entry.entry_model.value}")
        print(f"  Score     : {entry.confluence.score.value}")
        print(f"  Direction : {entry.confluence.signal.direction.value}")
        print(f"  Zone      : {entry.entry_zone_low:.5f} \u2013 {entry.entry_zone_high:.5f}")
        print(f"  CRT H4    : H={entry.confluence.signal.crt_high:.5f}  L={entry.confluence.signal.crt_low:.5f}")
        print(f"  M15 time  : {entry.time.isoformat()}")
    else:
        print(f"No entry signal for {pair} with min_score={settings.min_score.value}.")

    print("\nPhase 6 OK \u2713")


if __name__ == "__main__":
    asyncio.run(main())
