"""
Telegram alert output — formats EntrySignal objects and sends them via the Bot API.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime

import aiohttp

from core.models import Direction, EntrySignal

logger = logging.getLogger(__name__)

_SEND_MESSAGE_URL = "https://api.telegram.org/bot{token}/sendMessage"

# (pair, sweep_time, direction_value, entry_model_value)
AlertKey = tuple[str, datetime, str, str]


def format_alert(entry: EntrySignal) -> str:
    """
    Pure function. Returns a Markdown-formatted alert string for the given EntrySignal.
    No I/O. Safe to call from any context.
    """
    signal = entry.confluence.signal
    direction_emoji = "▲" if signal.direction == Direction.BULLISH else "▼"
    pair_display = entry.pair.replace("_", "/")
    score = entry.confluence.score.value

    kl = entry.confluence.key_level
    if kl is not None:
        kl_str = f"{kl.type.value} {kl.granularity}"
    else:
        kl_str = "—"

    m15_time = entry.time.strftime("%Y-%m-%d %H:%M")

    return (
        f"🔔 {pair_display} {direction_emoji} Score {score}\n"
        f"Entry Model: {entry.entry_model.value}\n"
        f"Zone: {entry.entry_zone_low:.5f} \u2013 {entry.entry_zone_high:.5f}\n"
        f"CRT H4: H {signal.crt_high:.5f} | L {signal.crt_low:.5f}\n"
        f"Key Level: {kl_str}\n"
        f"M15 @ {m15_time} UTC"
    )


class TelegramBot:
    """
    Async wrapper around the Telegram Bot sendMessage endpoint.

    Args:
        token:   Bot token from BotFather.
        chat_id: Destination chat or channel ID.
        session: An active aiohttp.ClientSession (caller owns lifecycle).
    """

    def __init__(
        self,
        token: str,
        chat_id: str,
        session: aiohttp.ClientSession,
    ) -> None:
        self._token = token
        self._chat_id = chat_id
        self._session = session
        self._sent: set[AlertKey] = set()

    def _alert_key(self, entry: EntrySignal) -> AlertKey:
        signal = entry.confluence.signal
        return (
            entry.pair,
            signal.sweep_time,
            signal.direction.value,
            entry.entry_model.value,
        )

    async def send_alert(self, entry: EntrySignal) -> None:
        """
        Format and POST the alert to Telegram.
        Deduplicates silently if the key was already sent.
        Logs errors without raising.
        Sleeps 1 second after each send attempt (rate limit).
        """
        key = self._alert_key(entry)
        if key in self._sent:
            logger.debug("send_alert: duplicate skipped for %s", key)
            return

        text = format_alert(entry)
        url = _SEND_MESSAGE_URL.format(token=self._token)
        payload = {
            "chat_id": self._chat_id,
            "text": text,
            "parse_mode": "Markdown",
        }

        try:
            async with self._session.post(url, json=payload) as resp:
                if resp.status == 200:
                    self._sent.add(key)
                    logger.info("send_alert: sent %s", key)
                else:
                    body = await resp.text()
                    logger.error(
                        "send_alert: Telegram returned %d: %s", resp.status, body[:200]
                    )
        except aiohttp.ClientError as exc:
            logger.error("send_alert: network error: %s", exc)
            return

        await asyncio.sleep(1)

    async def send_text(self, text: str) -> None:
        """Send a raw Markdown text string to Telegram. No deduplication."""
        url = _SEND_MESSAGE_URL.format(token=self._token)
        payload = {"chat_id": self._chat_id, "text": text, "parse_mode": "Markdown"}
        try:
            async with self._session.post(url, json=payload) as resp:
                if resp.status == 200:
                    logger.info("send_text: OK")
                else:
                    body = await resp.text()
                    logger.error(
                        "send_text: Telegram returned %d: %s", resp.status, body[:200]
                    )
        except aiohttp.ClientError as exc:
            logger.error("send_text: network error: %s", exc)
            return
        await asyncio.sleep(1)
