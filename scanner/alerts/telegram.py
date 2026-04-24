from __future__ import annotations

import requests

from scanner.config import settings


# Task 3.1
class AlertDeliveryError(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"Telegram delivery failed: {reason}")


# Tasks 3.2 – 3.4
def send_alert(text: str) -> None:
    """Send a pre-formatted HTML message to the configured Telegram chat.

    Raises AlertDeliveryError on any delivery failure.
    The bot token is NEVER included in error messages or logs.
    """
    # Task 3.2 — URL and payload construction
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": settings.TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    # Tasks 3.3 & 3.4 — send, handle errors, validate response
    try:
        response = requests.post(url, json=payload, timeout=10)
    except requests.exceptions.Timeout:
        raise AlertDeliveryError("request timed out") from None
    except requests.exceptions.ConnectionError:
        raise AlertDeliveryError("connection error") from None

    # Task 3.4a — HTTP status check
    if response.status_code != 200:
        raise AlertDeliveryError(f"HTTP {response.status_code}")

    # Task 3.4b — Telegram API ok flag
    body = response.json()
    if body.get("ok") is not True:
        raise AlertDeliveryError(f"API error: {body.get('description', 'unknown')}")

    return None
