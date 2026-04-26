from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from scanner.config import settings

logger = logging.getLogger(__name__)

_TRACKER_FILE = "tracker.json"
_FMT = "%Y-%m-%d %H:%M"


class AlertTracker:
    def __init__(self, tracker_dir: Path | None = None) -> None:
        if tracker_dir is None:
            tracker_dir = Path(settings.CACHE_DIR).resolve()
        self._path = tracker_dir / _TRACKER_FILE
        try:
            self._data: dict[str, dict[str, str]] = json.loads(
                self._path.read_text(encoding="utf-8")
            )
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            self._data = {}

    def is_active(self, symbol: str) -> bool:
        return symbol in self._data

    def mark_alerted(
        self, symbol: str, window_start: datetime, window_end: datetime
    ) -> None:
        self._data[symbol] = {
            "window_start": window_start.strftime(_FMT),
            "window_end": window_end.strftime(_FMT),
        }
        self._persist()

    def clear_if_expired(self, symbol: str) -> None:
        if symbol not in self._data:
            return
        window_end = datetime.strptime(self._data[symbol]["window_end"], _FMT)
        if datetime.now(timezone.utc).replace(tzinfo=None) > window_end:
            del self._data[symbol]
            self._persist()

    def _persist(self) -> None:
        tmp = self._path.with_suffix(".json.tmp")
        try:
            tmp.write_text(json.dumps(self._data), encoding="utf-8")
            tmp.replace(self._path)
        except OSError as e:
            logger.warning("Tracker write error: %s", e)
