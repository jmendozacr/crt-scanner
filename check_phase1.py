"""
Quick smoke-test for Phase 1.
Run: python check_phase1.py
Requires a valid .env file with TWELVEDATA_API_KEY.
"""
import asyncio
import logging

from config import settings
from data.twelvedata_client import TwelveDataClient
from data.candle_store import CandleStore

logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(name)s: %(message)s")


async def main() -> None:
    store = CandleStore(buffer_size=settings.candle_buffer_size)

    async with TwelveDataClient(settings) as client:
        print("\n=== Fetching historical candles for EUR_USD ===")
        for gran in ("D", "H4", "M15"):
            candles = await client.get_candles("EUR_USD", gran, count=5)
            store.update(candles)
            df = store.get_last("EUR_USD", gran, n=3)
            print(f"\n{gran} — last 3 complete candles:")
            print(df[["time", "open", "high", "low", "close", "complete"]].to_string(index=False))

    print("\nPhase 1 OK ✓")


if __name__ == "__main__":
    asyncio.run(main())
