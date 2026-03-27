"""Tests for core/fvg_detector.py"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from core.fvg_detector import detect_fvgs
from core.models import Direction, KeyLevelType

_T0 = datetime(2025, 1, 1, tzinfo=timezone.utc)


def _c(n, o, h, l, c, complete=True):
    return {"time": _T0 + timedelta(days=n), "open": o, "high": h, "low": l,
            "close": c, "volume": 0, "complete": complete}


def _df(*rows):
    return pd.DataFrame(list(rows))


class TestFVGDetector:
    def test_bullish_fvg(self):
        """Gap: c0.high=1.10 < c2.low=1.12 → bullish FVG zone 1.10–1.12."""
        df = _df(
            _c(0, 1.08, 1.10, 1.07, 1.09),  # c0: high=1.10
            _c(1, 1.09, 1.14, 1.09, 1.13),  # c1: impulse up
            _c(2, 1.12, 1.15, 1.12, 1.14),  # c2: low=1.12 > c0.high=1.10 → gap
        )
        fvgs = detect_fvgs(df, "EUR_USD", "D")
        assert len(fvgs) == 1
        fvg = fvgs[0]
        assert fvg.type == KeyLevelType.FVG
        assert fvg.direction == Direction.BULLISH
        assert fvg.low == pytest.approx(1.10)
        assert fvg.high == pytest.approx(1.12)

    def test_bearish_fvg(self):
        """Gap: c0.low=1.10 > c2.high=1.08 → bearish FVG zone 1.08–1.10."""
        df = _df(
            _c(0, 1.12, 1.13, 1.10, 1.11),  # c0: low=1.10
            _c(1, 1.11, 1.11, 1.06, 1.07),  # c1: impulse down
            _c(2, 1.08, 1.08, 1.05, 1.06),  # c2: high=1.08 < c0.low=1.10 → gap
        )
        fvgs = detect_fvgs(df, "EUR_USD", "D")
        assert len(fvgs) == 1
        fvg = fvgs[0]
        assert fvg.direction == Direction.BEARISH
        assert fvg.low == pytest.approx(1.08)
        assert fvg.high == pytest.approx(1.10)

    def test_no_fvg_when_overlapping(self):
        """Candles overlap — no FVG."""
        df = _df(
            _c(0, 1.08, 1.10, 1.07, 1.09),
            _c(1, 1.09, 1.12, 1.08, 1.11),
            _c(2, 1.10, 1.13, 1.09, 1.12),  # c2.low=1.09 < c0.high=1.10 → no gap
        )
        assert detect_fvgs(df, "EUR_USD", "D") == []

    def test_incomplete_candles_ignored(self):
        df = _df(
            _c(0, 1.08, 1.10, 1.07, 1.09),
            _c(1, 1.09, 1.14, 1.09, 1.13),
            _c(2, 1.12, 1.15, 1.12, 1.14, complete=False),
        )
        assert detect_fvgs(df, "EUR_USD", "D") == []

    def test_insufficient_data(self):
        df = _df(_c(0, 1.08, 1.10, 1.07, 1.09))
        assert detect_fvgs(df, "EUR_USD", "D") == []

    def test_fvg_time_is_middle_candle(self):
        """FVG time should be the middle (impulse) candle's timestamp."""
        df = _df(
            _c(0, 1.08, 1.10, 1.07, 1.09),
            _c(1, 1.09, 1.14, 1.09, 1.13),  # middle candle → day 1
            _c(2, 1.12, 1.15, 1.12, 1.14),
        )
        fvgs = detect_fvgs(df, "EUR_USD", "D")
        assert fvgs[0].time == _T0 + timedelta(days=1)
