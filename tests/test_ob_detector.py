"""Tests for core/ob_detector.py"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from core.ob_detector import detect_obs, detect_swings
from core.models import Direction, KeyLevelType

_T0 = datetime(2025, 1, 1, tzinfo=timezone.utc)


def _c(n, o, h, l, c, complete=True):
    return {"time": _T0 + timedelta(days=n), "open": o, "high": h, "low": l,
            "close": c, "volume": 0, "complete": complete}


def _df(*rows):
    return pd.DataFrame(list(rows))


class TestOBDetector:
    def test_bullish_ob(self):
        """Bearish candle followed by 2 bullish candles closing above OB high."""
        df = _df(
            _c(0, 1.12, 1.13, 1.08, 1.09),  # OB: bearish (open=1.12, close=1.09)
            _c(1, 1.09, 1.13, 1.09, 1.12),  # bullish
            _c(2, 1.12, 1.15, 1.12, 1.14),  # bullish, close=1.14 > OB.high=1.13
        )
        obs = detect_obs(df, "EUR_USD", "D")
        assert len(obs) == 1
        ob = obs[0]
        assert ob.type == KeyLevelType.ORDER_BLOCK
        assert ob.direction == Direction.BULLISH
        assert ob.low == pytest.approx(1.09)   # close of bearish OB
        assert ob.high == pytest.approx(1.12)  # open of bearish OB

    def test_bearish_ob(self):
        """Bullish candle followed by 2 bearish candles closing below OB low."""
        df = _df(
            _c(0, 1.09, 1.13, 1.09, 1.12),  # OB: bullish (open=1.09, close=1.12)
            _c(1, 1.12, 1.12, 1.09, 1.10),  # bearish
            _c(2, 1.10, 1.10, 1.06, 1.07),  # bearish, close=1.07 < OB.low=1.09
        )
        obs = detect_obs(df, "EUR_USD", "D")
        assert len(obs) == 1
        ob = obs[0]
        assert ob.direction == Direction.BEARISH
        assert ob.low == pytest.approx(1.09)   # open of bullish OB
        assert ob.high == pytest.approx(1.12)  # close of bullish OB

    def test_no_ob_without_impulse_break(self):
        """Bullish impulse doesn't close above OB high → no OB."""
        df = _df(
            _c(0, 1.12, 1.13, 1.08, 1.09),  # bearish OB candidate
            _c(1, 1.09, 1.12, 1.09, 1.11),  # bullish but close=1.11 < OB.high=1.13
            _c(2, 1.11, 1.12, 1.10, 1.12),  # bullish but close=1.12 < OB.high=1.13
        )
        assert detect_obs(df, "EUR_USD", "D") == []

    def test_incomplete_candle_ignored(self):
        df = _df(
            _c(0, 1.12, 1.13, 1.08, 1.09),
            _c(1, 1.09, 1.13, 1.09, 1.12),
            _c(2, 1.12, 1.15, 1.12, 1.14, complete=False),
        )
        # index 2 is incomplete so impulse[-1] is not there — no OB
        assert detect_obs(df, "EUR_USD", "D") == []


class TestSwingDetector:
    def test_swing_high(self):
        """Middle candle has the highest high → Swing High."""
        df = _df(
            _c(0, 1.10, 1.11, 1.09, 1.10),
            _c(1, 1.10, 1.11, 1.09, 1.10),
            _c(2, 1.10, 1.15, 1.09, 1.11),  # pivot high
            _c(3, 1.11, 1.12, 1.10, 1.11),
            _c(4, 1.11, 1.12, 1.10, 1.11),
        )
        swings = detect_swings(df, "EUR_USD", "D")
        highs = [s for s in swings if s.type == KeyLevelType.SWING_HIGH]
        assert len(highs) == 1
        assert highs[0].high == pytest.approx(1.15)
        assert highs[0].direction == Direction.BEARISH

    def test_swing_low(self):
        """Middle candle has the lowest low → Swing Low."""
        df = _df(
            _c(0, 1.10, 1.12, 1.09, 1.10),
            _c(1, 1.10, 1.12, 1.09, 1.10),
            _c(2, 1.10, 1.12, 1.05, 1.10),  # pivot low
            _c(3, 1.10, 1.12, 1.09, 1.10),
            _c(4, 1.10, 1.12, 1.09, 1.10),
        )
        swings = detect_swings(df, "EUR_USD", "D")
        lows = [s for s in swings if s.type == KeyLevelType.SWING_LOW]
        assert len(lows) == 1
        assert lows[0].low == pytest.approx(1.05)
        assert lows[0].direction == Direction.BULLISH

    def test_no_swing_when_not_pivot(self):
        df = _df(
            _c(0, 1.10, 1.14, 1.09, 1.10),  # already higher than middle
            _c(1, 1.10, 1.12, 1.09, 1.10),
            _c(2, 1.10, 1.13, 1.09, 1.10),  # not highest
            _c(3, 1.10, 1.12, 1.09, 1.10),
            _c(4, 1.10, 1.12, 1.09, 1.10),
        )
        highs = [s for s in detect_swings(df, "EUR_USD", "D") if s.type == KeyLevelType.SWING_HIGH]
        assert highs == []
