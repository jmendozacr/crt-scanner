"""
Unit tests for core/crt_detector.py using synthetic DataFrames.

Each test builds a minimal OHLCV DataFrame with hand-crafted candles
that should (or should not) trigger a specific CRT model.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from core.crt_detector import detect
from core.models import CRTModel, Direction

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_T0 = datetime(2025, 1, 1, tzinfo=timezone.utc)


def _candle(
    n: int,
    open_: float,
    high: float,
    low: float,
    close: float,
    complete: bool = True,
) -> dict:
    return {
        "time": _T0 + timedelta(hours=4 * n),
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": 1000,
        "complete": complete,
    }


def _df(*rows: dict) -> pd.DataFrame:
    return pd.DataFrame(list(rows))


PAIR = "EUR_USD"
GRAN = "H4"


# ---------------------------------------------------------------------------
# 2 Candle CRT
# ---------------------------------------------------------------------------

class TestTwoCandle:
    def test_bullish(self):
        """Sweep low of ref, close back above it."""
        df = _df(
            _candle(0, 1.10, 1.12, 1.08, 1.11),   # ref: range 1.08–1.12
            _candle(1, 1.11, 1.115, 1.07, 1.09),  # sweep: low=1.07 < 1.08 ✓, high=1.115 < 1.12 (no bearish)
        )
        signals = detect(df, PAIR, GRAN)
        assert len(signals) == 1
        s = signals[0]
        assert s.model == CRTModel.TWO_CANDLE
        assert s.direction == Direction.BULLISH
        assert s.crt_high == pytest.approx(1.12)
        assert s.crt_low == pytest.approx(1.08)

    def test_bearish(self):
        """Sweep high of ref, close back below it."""
        df = _df(
            _candle(0, 1.10, 1.12, 1.08, 1.11),  # ref: range 1.08–1.12
            _candle(1, 1.11, 1.14, 1.09, 1.11),  # sweep: high=1.14 > 1.12, close=1.11 < 1.12
        )
        signals = detect(df, PAIR, GRAN)
        assert len(signals) == 1
        s = signals[0]
        assert s.model == CRTModel.TWO_CANDLE
        assert s.direction == Direction.BEARISH

    def test_no_signal_when_no_sweep(self):
        """Candle stays within ref range — no CRT."""
        df = _df(
            _candle(0, 1.10, 1.12, 1.08, 1.11),
            _candle(1, 1.10, 1.11, 1.09, 1.10),  # within range
        )
        assert detect(df, PAIR, GRAN) == []

    def test_no_signal_when_closes_outside(self):
        """Sweep low but close stays below ref.low — not a valid CRT (no return)."""
        df = _df(
            _candle(0, 1.10, 1.12, 1.08, 1.11),
            _candle(1, 1.10, 1.11, 1.07, 1.075),  # low=1.07 swept, close=1.075 < 1.08
        )
        assert detect(df, PAIR, GRAN) == []

    def test_incomplete_candle_ignored(self):
        """An incomplete sweep candle must NOT trigger a signal."""
        df = _df(
            _candle(0, 1.10, 1.12, 1.08, 1.11),
            _candle(1, 1.11, 1.13, 1.07, 1.09, complete=False),  # would be bullish but incomplete
        )
        assert detect(df, PAIR, GRAN) == []

    def test_insufficient_data(self):
        """Single candle returns empty."""
        df = _df(_candle(0, 1.10, 1.12, 1.08, 1.11))
        assert detect(df, PAIR, GRAN) == []


# ---------------------------------------------------------------------------
# 3 Candle CRT
# ---------------------------------------------------------------------------

class TestThreeCandle:
    def test_bullish(self):
        """Manip sweeps low, dist closes back above ref.low."""
        df = _df(
            _candle(0, 1.10, 1.12, 1.08, 1.11),   # ref
            _candle(1, 1.11, 1.115, 1.06, 1.07),  # manip: low=1.06 < 1.08 ✓, high=1.115 < 1.12 (no bearish)
            _candle(2, 1.07, 1.11, 1.06, 1.10),   # dist: close=1.10 > ref.low=1.08 ✓
        )
        signals = detect(df, PAIR, GRAN)
        three = [s for s in signals if s.model == CRTModel.THREE_CANDLE]
        assert len(three) == 1
        assert three[0].direction == Direction.BULLISH

    def test_bearish(self):
        """Manip sweeps high, dist closes back below ref.high."""
        df = _df(
            _candle(0, 1.10, 1.12, 1.08, 1.11),  # ref
            _candle(1, 1.11, 1.15, 1.09, 1.14),  # manip: sweeps high (1.15 > 1.12), no return
            _candle(2, 1.14, 1.15, 1.09, 1.09),  # dist: close=1.09 < ref.high=1.12 ✓
        )
        signals = detect(df, PAIR, GRAN)
        three = [s for s in signals if s.model == CRTModel.THREE_CANDLE]
        assert len(three) == 1
        assert three[0].direction == Direction.BEARISH


# ---------------------------------------------------------------------------
# Inside Bar CRT
# ---------------------------------------------------------------------------

class TestInsideBar:
    def test_bullish(self):
        """Inside bar swept at low, sweep closes back above inside.low."""
        df = _df(
            _candle(0, 1.10, 1.15, 1.05, 1.12),  # outer
            _candle(1, 1.11, 1.13, 1.08, 1.12),  # inside bar (within outer)
            _candle(2, 1.12, 1.13, 1.07, 1.09),  # sweep: low=1.07 < inside.low=1.08, close=1.09 > 1.08
        )
        signals = detect(df, PAIR, GRAN)
        ib = [s for s in signals if s.model == CRTModel.INSIDE_BAR]
        assert len(ib) == 1
        assert ib[0].direction == Direction.BULLISH
        # CRT range = inside bar's range, not outer's
        assert ib[0].crt_high == pytest.approx(1.13)
        assert ib[0].crt_low == pytest.approx(1.08)

    def test_bearish(self):
        """Inside bar swept at high, sweep closes back below inside.high."""
        df = _df(
            _candle(0, 1.10, 1.15, 1.05, 1.12),  # outer
            _candle(1, 1.11, 1.13, 1.08, 1.12),  # inside bar
            _candle(2, 1.12, 1.14, 1.09, 1.12),  # sweep: high=1.14 > 1.13, close=1.12 < 1.13
        )
        signals = detect(df, PAIR, GRAN)
        ib = [s for s in signals if s.model == CRTModel.INSIDE_BAR]
        assert len(ib) == 1
        assert ib[0].direction == Direction.BEARISH

    def test_no_signal_when_not_inside_bar(self):
        """Middle candle is NOT an inside bar — no Inside Bar CRT."""
        df = _df(
            _candle(0, 1.10, 1.12, 1.08, 1.11),
            _candle(1, 1.11, 1.13, 1.07, 1.10),  # NOT inside bar (goes below outer.low)
            _candle(2, 1.10, 1.14, 1.06, 1.12),
        )
        ib = [s for s in detect(df, PAIR, GRAN) if s.model == CRTModel.INSIDE_BAR]
        assert ib == []


# ---------------------------------------------------------------------------
# Multi Candle CRT
# ---------------------------------------------------------------------------

class TestMultiCandle:
    def test_bullish_two_sweeps(self):
        """Ref + 2 sweep candles below ref.low + final closes back above."""
        df = _df(
            _candle(0, 1.10, 1.12, 1.08, 1.11),    # ref: low=1.08
            _candle(1, 1.11, 1.115, 1.07, 1.075),  # sweep1: low=1.07 < ref.low=1.08 ✓
            _candle(2, 1.075, 1.085, 1.07, 1.075), # sweep2: low=1.07 == sweep1.low (not inside-bar), < ref.low=1.08 ✓
            _candle(3, 1.075, 1.11, 1.06, 1.09),   # final: close=1.09 > ref.low=1.08 ✓
        )
        signals = detect(df, PAIR, GRAN)
        multi = [s for s in signals if s.model == CRTModel.MULTI_CANDLE]
        assert len(multi) >= 1
        assert any(s.direction == Direction.BULLISH for s in multi)

    def test_bearish_two_sweeps(self):
        """Ref + 2 sweep candles above ref.high + final closes back below."""
        df = _df(
            _candle(0, 1.10, 1.12, 1.08, 1.11),   # ref: high=1.12
            _candle(1, 1.11, 1.14, 1.09, 1.13),   # sweep1: high=1.14 > ref.high=1.12 ✓
            _candle(2, 1.13, 1.14, 1.10, 1.125),  # sweep2: high=1.14 == sweep1.high (not inside-bar), > ref.high=1.12 ✓
            _candle(3, 1.125, 1.15, 1.09, 1.11),  # final: close=1.11 < ref.high=1.12 ✓
        )
        signals = detect(df, PAIR, GRAN)
        multi = [s for s in signals if s.model == CRTModel.MULTI_CANDLE]
        assert any(s.direction == Direction.BEARISH for s in multi)


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

class TestDeduplication:
    def test_inside_bar_wins_over_two_candle(self):
        """Same sweep_time: INSIDE_BAR should win over TWO_CANDLE."""
        df = _df(
            _candle(0, 1.10, 1.15, 1.05, 1.12),  # outer
            _candle(1, 1.11, 1.13, 1.08, 1.12),  # inside bar
            _candle(2, 1.12, 1.13, 1.07, 1.09),  # sweep (also qualifies as TWO_CANDLE vs inside)
        )
        signals = detect(df, PAIR, GRAN)
        bullish = [s for s in signals if s.direction == Direction.BULLISH]
        # Only one signal per (sweep_time, direction)
        assert len(bullish) == 1
        assert bullish[0].model == CRTModel.INSIDE_BAR
