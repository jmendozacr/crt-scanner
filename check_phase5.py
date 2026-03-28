"""
Smoke-test for Phase 5: Telegram alert formatting and optional send.
Run: python check_phase5.py          # safe — prints formatted alert only
Run: python check_phase5.py --send   # also sends one alert to Telegram
"""
import argparse
import asyncio
import logging
import sys

sys.stdout.reconfigure(encoding="utf-8")

import aiohttp

from config import settings
from data.twelvedata_client import TwelveDataClient
from data.candle_store import CandleStore
from core.crt_detector import detect
from core.htf_confluence import run_confluence
from core.entry_models import find_entry
from core.models import Score
from output.telegram_bot import TelegramBot, format_alert

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")


async def main(send: bool) -> None:
    store = CandleStore(buffer_size=settings.candle_buffer_size)
    pair = settings.pairs[0]

    async with TwelveDataClient(settings) as client:
        print(f"Fetching D + H4 + M15 for {pair}...\n")
        for gran in ("D", "H4", "M15"):
            candles = await client.get_candles(pair, gran, count=100)
            store.update(candles)
            await asyncio.sleep(8)

    entry = _find_first_entry(store, pair)
    if entry is None:
        print(f"No entry signal found for {pair}.")
        return

    msg = format_alert(entry)
    print("=== Formatted Alert ===")
    print(msg)
    print()

    if send:
        async with aiohttp.ClientSession() as session:
            bot = TelegramBot(
                token=settings.telegram_bot_token,
                chat_id=settings.telegram_chat_id,
                session=session,
            )
            await bot.send_alert(entry)
            print("Alert sent to Telegram.")
    else:
        print("(Pass --send to actually send to Telegram)")

    print("\nPhase 5 OK ✓")


def _find_first_entry(store, pair):
    h4_signals = detect(store.get(pair, "H4"), pair, "H4")
    results = run_confluence(h4_signals[-5:], store, pair)
    m15_df = store.get(pair, "M15")
    for conf in results:
        if conf.score == Score.A:
            entry = find_entry(conf, m15_df)
            if entry:
                return entry
    for conf in results:
        entry = find_entry(conf, m15_df)
        if entry:
            return entry
    return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--send", action="store_true", help="Send alert to Telegram")
    args = parser.parse_args()
    asyncio.run(main(send=args.send))
