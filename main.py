"""
CRT Scanner — main orchestration loop.

Bootstrap: fetches 100 candles of D + H4 + M15 for all pairs on startup.
Polling:   runs poll_candles() indefinitely; fires the detection pipeline
           for every pair that receives a new closed M15 candle.

Run:  python main.py
Stop: Ctrl+C
"""
from __future__ import annotations

import asyncio
import logging
import sys
from typing import TYPE_CHECKING

import aiohttp

from config import MinScore, settings
from core.crt_detector import detect
from core.entry_models import find_entry
from core.htf_confluence import run_confluence
from core.models import EntrySignal, Score
from data.candle_store import CandleStore
from data.twelvedata_client import Candle, TwelveDataClient
from output.telegram_bot import TelegramBot

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Score filter
# ---------------------------------------------------------------------------

_SCORE_ORDER: dict[Score, int] = {Score.A: 2, Score.B: 1}
_MIN_SCORE_ORDER: dict[MinScore, int] = {MinScore.A: 2, MinScore.B: 1}


def _passes_filter(conf, min_score: MinScore) -> bool:
    return _SCORE_ORDER[conf.score] >= _MIN_SCORE_ORDER[min_score]


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def _configure_logging() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

async def _bootstrap(
    client: TwelveDataClient,
    store: CandleStore,
    pairs: list[str],
) -> None:
    """One-shot startup: populate the store with 100 candles per pair × granularity."""
    granularities = ("D", "H4", "M15")
    total = len(pairs) * len(granularities)
    count = 0
    logger.info("Bootstrap started — %d pairs × %d granularities (%d requests)",
                len(pairs), len(granularities), total)

    for pair in pairs:
        for gran in granularities:
            candles = await client.get_candles(pair, gran, count=100)
            store.update(candles)
            count += 1
            if count < total:
                await asyncio.sleep(8)
        logger.info("Bootstrap complete for %s", pair)

    logger.info("Bootstrap finished — store ready")


# ---------------------------------------------------------------------------
# Per-pair pipeline
# ---------------------------------------------------------------------------

async def _process_pair(
    pair: str,
    store: CandleStore,
    bot: TelegramBot | None,
    min_score: MinScore,
) -> EntrySignal | None:
    """
    Run the full detection pipeline for one pair.
    Returns the first EntrySignal found, or None.
    bot=None suppresses Telegram sends (used by check_phase6.py).
    """
    h4_df = store.get(pair, "H4")
    signals = detect(h4_df, pair, "H4")
    if not signals:
        return None

    confluence_results = run_confluence(signals[-5:], store, pair)
    if not confluence_results:
        return None

    m15_df = store.get(pair, "M15")
    for conf in confluence_results:
        if not _passes_filter(conf, min_score):
            continue
        entry = find_entry(conf, m15_df)
        if entry is None:
            continue
        logger.info("Entry signal: %r", entry)
        if bot is not None:
            await bot.send_alert(entry)
        return entry

    return None


# ---------------------------------------------------------------------------
# Poll callback
# ---------------------------------------------------------------------------

async def _on_candles(
    candles: list[Candle],
    store: CandleStore,
    bot: TelegramBot,
    min_score: MinScore,
) -> None:
    """Callback invoked by poll_candles() with each batch of new closed candles."""
    store.update(candles)

    m15_pairs: set[str] = {c.pair for c in candles if c.granularity == "M15"}
    if not m15_pairs:
        return

    logger.info("New M15 candles for: %s", sorted(m15_pairs))
    for pair in sorted(m15_pairs):
        try:
            await _process_pair(pair, store, bot, min_score)
        except Exception as exc:
            logger.error("Pipeline error for %s: %s", pair, exc, exc_info=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> None:
    _configure_logging()
    logger.info(
        "CRT Scanner starting — pairs=%s min_score=%s",
        settings.pairs,
        settings.min_score.value,
    )

    store = CandleStore(buffer_size=settings.candle_buffer_size)
    poll_task: asyncio.Task | None = None

    async with aiohttp.ClientSession() as http_session:
        bot = TelegramBot(
            token=settings.telegram_bot_token,
            chat_id=settings.telegram_chat_id,
            session=http_session,
        )

        async with TwelveDataClient(settings) as client:
            await _bootstrap(client, store, settings.pairs)

            async def on_candles(candles: list[Candle]) -> None:
                await _on_candles(candles, store, bot, settings.min_score)

            poll_task = asyncio.create_task(
                client.poll_candles(
                    pairs=settings.pairs,
                    granularities=["D", "H4", "M15"],
                    callback=on_candles,
                )
            )
            logger.info("Polling loop started (interval ~900s).")

            try:
                await poll_task
            except asyncio.CancelledError:
                logger.info("Poll task cancelled — shutting down.")
            finally:
                if poll_task and not poll_task.done():
                    poll_task.cancel()
                    try:
                        await poll_task
                    except asyncio.CancelledError:
                        pass
                logger.info("Shutdown complete.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nScanner stopped.")
