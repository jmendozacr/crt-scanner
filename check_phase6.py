"""
End-to-end smoke test for the Clutifx pipeline (refactored main.py).
Bootstraps the first pair, runs H4 + M15 cycles, prints active setups.
No Telegram messages are sent (bot=None).

Run: python check_phase6.py
"""
import asyncio
import logging
import sys

sys.stdout.reconfigure(encoding="utf-8")

from config import settings
from data.twelvedata_client import TwelveDataClient
from data.candle_store import CandleStore
from main import _active_setups, _bootstrap, _on_h4_close, _on_m15_close

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

    print(f"Running H4 detection for {pair} (min_score={settings.min_score.value})...\n")
    _on_h4_close(pair, store, settings.min_score)

    setups = _active_setups.get(pair, [])
    if setups:
        print(f"Active setups found: {len(setups)}")
        for s in setups:
            kl = s.htf_level
            kl_str = f"{kl.type.value} {kl.granularity}" if kl else "none (Score B)"
            print(
                f"  [{s.direction.upper():7}] crt_h={s.crt_h:.5f}  crt_l={s.crt_l:.5f}"
                f"  htf={kl_str}  expires={s.expires_at}"
            )

        print(f"\nRunning M15 OB detection for {pair}...")
        await _on_m15_close(pair, store, bot=None)

        for s in setups:
            if s.ob:
                print(
                    f"  [{s.direction.upper():7}] OB formed: {s.ob.low:.5f} – {s.ob.high:.5f}"
                    f"  status={s.status}"
                )
            else:
                print(f"  [{s.direction.upper():7}] No OB found yet  status={s.status}")
    else:
        print(f"No active setups for {pair} with min_score={settings.min_score.value}.")

    print("\nPhase 6 OK ✓")


if __name__ == "__main__":
    asyncio.run(main())
