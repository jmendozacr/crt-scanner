from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

_NY_TZ = ZoneInfo("America/New_York")
_UTC_TZ = ZoneInfo("UTC")
_FMT = "%Y-%m-%d %H:%M:%S"
_SESSIONS: list[tuple[str, time, time]] = [
    ("London Open", time(2, 0),  time(5, 0)),
    ("NY AM",       time(8, 30), time(11, 0)),
    ("NY PM",       time(13, 0), time(15, 0)),
]


def get_session(utc_dt_str: str) -> str | None:
    dt = datetime.strptime(utc_dt_str, _FMT).replace(tzinfo=_UTC_TZ)
    t = dt.astimezone(_NY_TZ).time()
    for name, start, end in _SESSIONS:
        if start <= t < end:
            return name
    return None
