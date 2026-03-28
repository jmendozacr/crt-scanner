"""
Unit tests for core/entry_model.py — Clutifx M15 OB detection.

Each test builds a minimal M15 DataFrame with synthetic candles.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

import pandas as pd
import pytest

from core.entry_model import find_engulfing_ob, check_ob_invalidation, check_ob_touch
from core.crt_detector import CRTSetup, OBLevel

_T0 = datetime(2025, 1, 1, tzinfo=timezone.utc)
PAIR = "EUR_USD"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _m(n: int, o: float, h: float, l: float, c: float) -> dict:
    """M15 candle at T0 + n*15 minutes."""
    return {
        "time": _T0 + timedelta(minutes=15 * n),
        "open": o, "high": h, "low": l, "close": c,
        "volume": 0, "complete": True,
    }


def _df(*rows: dict) -> pd.DataFrame:
    return pd.DataFrame(list(rows))


def _h4(n: int = 0) -> pd.Series:
    """Minimal H4 candle at T0 + n*4h."""
    return pd.Series({
        "time": _T0 + timedelta(hours=4 * n),
        "open": 1.10, "high": 1.13, "low": 1.08, "close": 1.115,
        "volume": 0, "complete": True,
    })


def _setup(direction: str, h4_n: int = 0) -> CRTSetup:
    """Minimal CRTSetup with expires_at = sweep["time"] + 4h."""
    sweep = _h4(h4_n)
    return CRTSetup(
        pair=PAIR,
        direction=direction,
        ref_candle=_h4(h4_n - 1),
        sweep_candle=sweep,
        crt_h=1.13,
        crt_l=1.08,
        expires_at=sweep["time"] + pd.Timedelta(hours=4),
    )


# ---------------------------------------------------------------------------
# find_engulfing_ob — bearish
# ---------------------------------------------------------------------------

class TestFindEngulfingObBearish:
    def test_bearish_simple(self):
        """Bullish M15 followed by bearish engulfing → OBLevel with c1 range."""
        setup = _setup("bearish")
        df = _df(
            _m(0, 1.100, 1.115, 1.095, 1.113),  # c1 bullish: h=1.115, l=1.095
            _m(1, 1.113, 1.120, 1.090, 1.100),  # c2 bearish engulfing
        )
        ob = find_engulfing_ob(df, setup)
        assert ob is not None
        assert ob.high == pytest.approx(1.115)   # c1.high
        assert ob.low  == pytest.approx(1.095)   # c1.low
        assert ob.formed_at == pd.Timestamp(_T0 + timedelta(minutes=15))  # c2 time

    def test_bearish_no_engulf_returns_none(self):
        """Bearish c2 does NOT engulf c1 (high < c1.high) → None."""
        setup = _setup("bearish")
        df = _df(
            _m(0, 1.100, 1.115, 1.095, 1.113),  # bullish
            _m(1, 1.113, 1.114, 1.096, 1.105),  # bearish but h=1.114 < c1.h=1.115 → no engulf
        )
        assert find_engulfing_ob(df, setup) is None

    def test_bearish_takes_last_occurrence(self):
        """Two valid bearish engulfing pairs → OB zone from last c1, formed_at = last c2."""
        setup = _setup("bearish")
        df = _df(
            _m(0, 1.100, 1.110, 1.095, 1.108),  # c1a bullish
            _m(1, 1.108, 1.115, 1.090, 1.095),  # c2a bearish engulf
            _m(2, 1.095, 1.105, 1.088, 1.102),  # c1b bullish: h=1.105, l=1.088
            _m(3, 1.102, 1.112, 1.085, 1.090),  # c2b bearish engulf → final OB = c1b range
        )
        ob = find_engulfing_ob(df, setup)
        assert ob is not None
        assert ob.high == pytest.approx(1.105)   # c1b.high
        assert ob.low  == pytest.approx(1.088)   # c1b.low
        assert ob.formed_at == pd.Timestamp(_T0 + timedelta(minutes=45))  # c2b time

    def test_bearish_out_of_window_returns_none(self):
        """M15 candle exactly at expires_at is excluded (window is half-open)."""
        setup = _setup("bearish")
        # expires_at = T0 + 4h = T0 + 240min. Put engulfing pair starting at minute 239.
        # But 239 min = candle 15, 240 min = candle 16 (outside window)
        df = _df(
            _m(15, 1.100, 1.115, 1.095, 1.113),  # T0 + 225 min — in window
            _m(16, 1.113, 1.120, 1.090, 1.100),  # T0 + 240 min = expires_at — excluded
        )
        assert find_engulfing_ob(df, setup) is None

    def test_too_few_candles_returns_none(self):
        """Only 1 M15 candle in window → None."""
        setup = _setup("bearish")
        df = _df(_m(0, 1.100, 1.115, 1.095, 1.113))
        assert find_engulfing_ob(df, setup) is None


# ---------------------------------------------------------------------------
# find_engulfing_ob — bullish
# ---------------------------------------------------------------------------

class TestFindEngulfingObBullish:
    def test_bullish_simple(self):
        """Bearish M15 followed by bullish engulfing → OBLevel with c1 range."""
        setup = _setup("bullish")
        df = _df(
            _m(0, 1.113, 1.120, 1.090, 1.100),  # c1 bearish: h=1.120, l=1.090
            _m(1, 1.100, 1.125, 1.085, 1.118),  # c2 bullish engulfing
        )
        ob = find_engulfing_ob(df, setup)
        assert ob is not None
        assert ob.high == pytest.approx(1.120)   # c1.high
        assert ob.low  == pytest.approx(1.090)   # c1.low
        assert ob.formed_at == pd.Timestamp(_T0 + timedelta(minutes=15))  # c2 time

    def test_bullish_no_engulf_returns_none(self):
        """Bullish c2 does NOT engulf c1 (low > c1.low) → None."""
        setup = _setup("bullish")
        df = _df(
            _m(0, 1.113, 1.120, 1.090, 1.100),  # bearish
            _m(1, 1.100, 1.121, 1.091, 1.118),  # bullish but l=1.091 > c1.l=1.090 → no engulf
        )
        assert find_engulfing_ob(df, setup) is None


# ---------------------------------------------------------------------------
# check_ob_invalidation
# ---------------------------------------------------------------------------

class TestCheckObInvalidation:
    def _ob(self) -> OBLevel:
        return OBLevel(high=1.120, low=1.090, formed_at=pd.Timestamp(_T0))

    def test_bearish_invalidated_when_close_above_high(self):
        """Bearish OB: candle closes above ob.high → True."""
        ob = self._ob()
        df = _df(
            _m(1, 1.110, 1.125, 1.108, 1.122),  # close=1.122 > ob.high=1.120
        )
        assert check_ob_invalidation(df, ob, "bearish") is True

    def test_bearish_not_invalidated_when_close_below_high(self):
        """Bearish OB: candle closes at or below ob.high → False."""
        ob = self._ob()
        df = _df(
            _m(1, 1.110, 1.125, 1.108, 1.119),  # close=1.119 < ob.high=1.120
        )
        assert check_ob_invalidation(df, ob, "bearish") is False

    def test_bullish_invalidated_when_close_below_low(self):
        """Bullish OB: candle closes below ob.low → True."""
        ob = self._ob()
        df = _df(
            _m(1, 1.095, 1.098, 1.085, 1.088),  # close=1.088 < ob.low=1.090
        )
        assert check_ob_invalidation(df, ob, "bullish") is True

    def test_bullish_not_invalidated_when_close_above_low(self):
        """Bullish OB: candle closes at or above ob.low → False."""
        ob = self._ob()
        df = _df(
            _m(1, 1.095, 1.098, 1.085, 1.091),  # close=1.091 > ob.low=1.090
        )
        assert check_ob_invalidation(df, ob, "bullish") is False

    def test_candles_before_formed_at_ignored(self):
        """Candle AT formed_at is not evaluated (only strictly after)."""
        ob = self._ob()  # formed_at = T0
        df = _df(
            _m(0, 1.110, 1.125, 1.108, 1.125),  # AT T0 — same time, excluded
        )
        assert check_ob_invalidation(df, ob, "bearish") is False


# ---------------------------------------------------------------------------
# check_ob_touch
# ---------------------------------------------------------------------------

class TestCheckObTouch:
    def _ob(self) -> OBLevel:
        return OBLevel(high=1.120, low=1.095, formed_at=pd.Timestamp(_T0))

    def test_bearish_touch_when_high_reaches_ob_low(self):
        """Bearish: candle high >= ob.low → touch (price re-entered zone)."""
        ob = self._ob()
        df = _df(
            _m(1, 1.091, 1.096, 1.089, 1.093),  # high=1.096 >= ob.low=1.095
        )
        assert check_ob_touch(df, ob, "bearish") is True

    def test_bearish_no_touch_when_high_below_ob_low(self):
        """Bearish: candle high < ob.low → no touch."""
        ob = self._ob()
        df = _df(
            _m(1, 1.091, 1.094, 1.089, 1.093),  # high=1.094 < ob.low=1.095
        )
        assert check_ob_touch(df, ob, "bearish") is False

    def test_bullish_touch_when_low_reaches_ob_high(self):
        """Bullish: candle low <= ob.high → touch."""
        ob = self._ob()
        df = _df(
            _m(1, 1.123, 1.126, 1.119, 1.124),  # low=1.119 <= ob.high=1.120
        )
        assert check_ob_touch(df, ob, "bullish") is True

    def test_bullish_no_touch_when_low_above_ob_high(self):
        """Bullish: candle low > ob.high → no touch."""
        ob = self._ob()
        df = _df(
            _m(1, 1.123, 1.126, 1.121, 1.124),  # low=1.121 > ob.high=1.120
        )
        assert check_ob_touch(df, ob, "bullish") is False

    def test_candles_before_formed_at_ignored(self):
        """Candle AT formed_at is not counted for touch (strictly after)."""
        ob = self._ob()  # formed_at = T0
        df = _df(
            _m(0, 1.091, 1.096, 1.089, 1.093),  # AT T0 — excluded
        )
        assert check_ob_touch(df, ob, "bearish") is False
