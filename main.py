"""
CRT Scanner — main orchestration loop (Clutifx refactor).

State machine per pair:
    H4 close  → detect_crt() → HTF confluence → active_setups[]
    M15 close → for each active setup:
                  "watching_m15" → find_engulfing_ob()
                  "ob_formed"    → check_ob_invalidation() | check_ob_touch()

Run:  python main.py
Stop: Ctrl+C
"""
from __future__ import annotations

import asyncio
import logging
import sys

import aiohttp
import pandas as pd

from config import MinScore, settings
from core.crt_detector import CRTSetup, detect_crt
from core.entry_model import find_engulfing_ob
from core.htf_confluence import get_key_levels
from core.models import Direction, KeyLevel
from data.candle_store import CandleStore
from data.twelvedata_client import Candle, TwelveDataClient
from output.telegram_bot import TelegramBot

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------

# Active setups awaiting M15 entry confirmation, keyed by pair
_active_setups: dict[str, list[CRTSetup]] = {}

# ---------------------------------------------------------------------------
# HTF confluence adapter for CRTSetup
# ---------------------------------------------------------------------------

_DEFAULT_TOL_RATIO = 0.1


def _check_setup_confluence(
    setup: CRTSetup,
    key_levels: list[KeyLevel],
) -> KeyLevel | None:
    """
    Check whether `setup` aligns with any HTF Daily key level.

    Bearish → checks crt_h against bearish key levels.
    Bullish → checks crt_l against bullish key levels.

    Returns the most-recent matching KeyLevel, or None (Score B).
    """
    crt_range = setup.crt_h - setup.crt_l
    tol = _DEFAULT_TOL_RATIO * crt_range

    wanted = Direction.BEARISH if setup.direction == "bearish" else Direction.BULLISH
    price  = setup.crt_h if setup.direction == "bearish" else setup.crt_l

    candidates = [
        kl for kl in key_levels
        if kl.direction == wanted
        and (kl.low - tol) <= price <= (kl.high + tol)
    ]
    return max(candidates, key=lambda kl: kl.time) if candidates else None


# ---------------------------------------------------------------------------
# Alert formatting
# ---------------------------------------------------------------------------

def _build_alert(setup: CRTSetup) -> str:
    dir_emoji = "🔻" if setup.direction == "bearish" else "🔺"
    pair_fmt  = setup.pair.replace("_", "/")

    kl = setup.htf_level
    kl_str = (
        f"{kl.type.value} {kl.granularity} ({kl.low:.5f} – {kl.high:.5f})"
        if kl is not None else "—"
    )

    ob = setup.ob
    ob_str  = f"{ob.low:.5f} – {ob.high:.5f}" if ob else "—"
    ob_time = ob.formed_at.strftime("%Y-%m-%d %H:%M")  if ob else "—"

    return (
        f"🔔 *CRT + CLUTIFX SETUP*\n\n"
        f"Par:        {pair_fmt}\n"
        f"Dirección:  {setup.direction.upper()} {dir_emoji}\n"
        f"Key Level:  {kl_str}\n"
        f"CRT H:      {setup.crt_h:.5f}\n"
        f"CRT L:      {setup.crt_l:.5f}\n"
        f"OB M15:     {ob_str}\n"
        f"Entrada:    Retroceso al OB\n"
        f"Hora UTC:   {ob_time}"
    )


# ---------------------------------------------------------------------------
# H4 cycle — detect + confluence + register
# ---------------------------------------------------------------------------

def _on_h4_close(pair: str, store: CandleStore, min_score: MinScore) -> None:
    """Detect new CRTs on the last closed H4 candle and add to active_setups."""
    h4_df = store.get(pair, "H4")
    new_setups = detect_crt(h4_df, pair)
    if not new_setups:
        return

    key_levels = get_key_levels(store, pair)
    now = pd.Timestamp.utcnow()

    for setup in new_setups:
        level = _check_setup_confluence(setup, key_levels)

        if min_score == MinScore.A and level is None:
            continue  # filtered out — no Score-A level found

        setup.htf_level = level
        setup.status = "watching_m15"

        # Avoid duplicate registrations for same (pair, sweep_time, direction)
        sweep_time = setup.sweep_candle["time"]
        existing = _active_setups.get(pair, [])
        already = any(
            s.direction == setup.direction and s.sweep_candle["time"] == sweep_time
            for s in existing
        )
        if not already:
            _active_setups.setdefault(pair, []).append(setup)
            logger.info(
                "New setup: %s %s crt_h=%.5f crt_l=%.5f htf=%s",
                pair, setup.direction, setup.crt_h, setup.crt_l,
                level.type.value if level else "none",
            )

    # Prune expired and resolved setups
    _active_setups[pair] = [
        s for s in _active_setups.get(pair, [])
        if s.expires_at > now
        and s.status not in ("triggered", "invalidated")
    ]


# ---------------------------------------------------------------------------
# M15 cycle — OB detection + touch / invalidation
# ---------------------------------------------------------------------------

async def _on_m15_close(
    pair: str,
    store: CandleStore,
    bot: TelegramBot | None,
) -> None:
    """Process active setups for `pair` on each new M15 candle."""
    if not _active_setups.get(pair):
        return

    m15_df = store.get(pair, "M15")
    if m15_df.empty:
        return

    for setup in list(_active_setups.get(pair, [])):
        if setup.status == "watching_m15":
            ob = find_engulfing_ob(m15_df, setup)
            if ob:
                setup.ob     = ob
                setup.status = "triggered"
                logger.info(
                    "%s %s OB formed: %.5f – %.5f @ %s — sending alert",
                    pair, setup.direction, ob.low, ob.high, ob.formed_at,
                )
                if bot is not None:
                    await bot.send_text(_build_alert(setup))


# ---------------------------------------------------------------------------
# Poll callback
# ---------------------------------------------------------------------------

async def _on_candles(
    candles: list[Candle],
    store: CandleStore,
    bot: TelegramBot,
    min_score: MinScore,
) -> None:
    """Callback invoked by poll_candles() for each batch of new closed candles."""
    store.update(candles)

    h4_pairs:  set[str] = {c.pair for c in candles if c.granularity == "H4"}
    m15_pairs: set[str] = {c.pair for c in candles if c.granularity == "M15"}

    for pair in sorted(h4_pairs):
        try:
            _on_h4_close(pair, store, min_score)
        except Exception as exc:
            logger.error("H4 pipeline error for %s: %s", pair, exc, exc_info=True)

    if m15_pairs:
        logger.info("New M15 candles for: %s", sorted(m15_pairs))
        for pair in sorted(m15_pairs):
            try:
                await _on_m15_close(pair, store, bot)
            except Exception as exc:
                logger.error("M15 pipeline error for %s: %s", pair, exc, exc_info=True)


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

async def _bootstrap(
    client: TwelveDataClient,
    store: CandleStore,
    pairs: list[str],
) -> None:
    """One-shot startup: populate the store with 100 candles per pair × granularity.

    Uses individual requests (1 API credit each) with a 9-second delay between
    them to stay under the Twelve Data free-tier limit of 8 credits/minute.
    If a rate-limit error occurs (e.g. due to a restart mid-minute) the
    bootstrap waits 65 seconds and retries instead of crashing.
    """
    granularities = ("D", "H4", "M15")
    total = len(pairs) * len(granularities)
    logger.info(
        "Bootstrap started — %d pairs × %d granularities (%d requests, ~%ds)",
        len(pairs), len(granularities), total, total * 9,
    )

    count = 0
    for pair in pairs:
        for gran in granularities:
            while True:
                try:
                    candles = await client.get_candles(pair, gran, count=100)
                    store.update(candles)
                    break
                except RuntimeError as exc:
                    if "run out of API credits" in str(exc):
                        logger.warning(
                            "Rate limit hit during bootstrap — waiting 65s before retry"
                        )
                        await asyncio.sleep(65)
                    else:
                        raise
            count += 1
            if count < total:
                await asyncio.sleep(9)
        logger.info("Bootstrap complete for %s", pair)

    logger.info("Bootstrap finished — store ready")


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
            logger.info("Polling loop started.")

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
