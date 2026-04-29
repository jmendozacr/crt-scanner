"""Tests for scanner.utils.sessions — SC-SES-1..7 (including DST)."""
from __future__ import annotations

import pytest

from scanner.utils.sessions import get_session


# SC-SES-1
def test_london_open() -> None:
    # 2024-01-15 07:30 UTC = 02:30 EST → London Open [02:00, 05:00)
    assert get_session("2024-01-15 07:30:00") == "London Open"


# SC-SES-2
def test_ny_am() -> None:
    # 2024-01-15 14:00 UTC = 09:00 EST → NY AM [08:30, 11:00)
    assert get_session("2024-01-15 14:00:00") == "NY AM"


# SC-SES-3
def test_ny_pm() -> None:
    # 2024-01-15 19:00 UTC = 14:00 EST → NY PM [13:00, 15:00)
    assert get_session("2024-01-15 19:00:00") == "NY PM"


# SC-SES-4
def test_outside_all() -> None:
    # 2024-01-15 12:00 UTC = 07:00 EST → no session
    assert get_session("2024-01-15 12:00:00") is None


# SC-SES-5
def test_boundary_excluded() -> None:
    # 2024-01-15 10:00 UTC = 05:00 EST exactly → excluded (half-open interval)
    assert get_session("2024-01-15 10:00:00") is None


# SC-SES-6
def test_dst_summer() -> None:
    # 2024-06-15 (EDT = UTC-4): 12:30 UTC = 08:30 EDT → NY AM
    assert get_session("2024-06-15 12:30:00") == "NY AM"


# SC-SES-7
def test_dst_winter() -> None:
    # 2024-01-15 (EST = UTC-5): 13:30 UTC = 08:30 EST → NY AM
    assert get_session("2024-01-15 13:30:00") == "NY AM"
