"""Tests for core/entry_models.py"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from core.entry_models import find_entry
from core.models import (
    CRTModel, CRTSignal, Direction, ConfluenceResult,
    EntryModel, EntrySignal, KeyLevel, KeyLevelType, Score,
)

_T0 = datetime(2025, 1, 1, tzinfo=timezone.utc)
PAIR = "EUR_USD"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _c(n, o, h, l, c, complete=True):
    return {"time": _T0 + timedelta(minutes=15 * n), "open": o, "high": h,
            "low": l, "close": c, "volume": 0, "complete": complete}


def _df(*rows):
    return pd.DataFrame(list(rows))


def _confluence(direction: Direction, crt_hi: float, crt_lo: float) -> ConfluenceResult:
    signal = CRTSignal(
        model=CRTModel.TWO_CANDLE,
        direction=direction,
        crt_high=crt_hi,
        crt_low=crt_lo,
        ref_time=_T0,
        sweep_time=_T0 + timedelta(hours=4),
        pair=PAIR,
        granularity="H4",
    )
    kl = KeyLevel(KeyLevelType.FVG, direction, crt_hi, crt_lo, _T0, PAIR, "D")
    return ConfluenceResult(signal=signal, key_level=kl, score=Score.A, aligned=True)


# CRT zone used in most tests: 1.08 – 1.12
_BULL = _confluence(Direction.BULLISH, crt_hi=1.12, crt_lo=1.08)
_BEAR = _confluence(Direction.BEARISH, crt_hi=1.12, crt_lo=1.08)


# ---------------------------------------------------------------------------
# OB entry
# ---------------------------------------------------------------------------

class TestOBEntry:
    def test_bullish_ob_in_zone(self):
        """Bearish candle → 2 bullish impulse above OB high, OB zone inside CRT range."""
        df = _df(
            _c(0, 1.11, 1.115, 1.09, 1.095),  # OB: bearish, body 1.09–1.11
            _c(1, 1.095, 1.11, 1.095, 1.10),  # bullish impulse 1
            _c(2, 1.10, 1.125, 1.10, 1.12),   # bullish impulse 2, closes above OB high=1.115 ✓
        )
        result = find_entry(_BULL, df)
        assert result is not None
        assert result.entry_model == EntryModel.ORDER_BLOCK

    def test_bearish_ob_in_zone(self):
        """Bullish candle → 2 bearish impulse below OB low, OB zone inside CRT range."""
        df = _df(
            _c(0, 1.09, 1.11, 1.09, 1.10),   # OB: bullish, body 1.09–1.10
            _c(1, 1.10, 1.10, 1.09, 1.095),  # bearish impulse 1
            _c(2, 1.095, 1.095, 1.07, 1.075),# bearish impulse 2, closes below OB low=1.09 ✓
        )
        result = find_entry(_BEAR, df)
        assert result is not None
        assert result.entry_model == EntryModel.ORDER_BLOCK


# ---------------------------------------------------------------------------
# FVG entry
# ---------------------------------------------------------------------------

class TestFVGEntry:
    def test_bullish_fvg_in_zone(self):
        """Gap between c0.high=1.09 and c2.low=1.10 → bullish FVG inside CRT range."""
        df = _df(
            _c(0, 1.08, 1.09, 1.08, 1.085),
            _c(1, 1.085, 1.12, 1.085, 1.11),  # impulse
            _c(2, 1.10, 1.115, 1.10, 1.11),   # c2.low=1.10 > c0.high=1.09 → gap
        )
        result = find_entry(_BULL, df)
        assert result is not None
        assert result.entry_model == EntryModel.FVG
        assert result.entry_zone_low == pytest.approx(1.09)
        assert result.entry_zone_high == pytest.approx(1.10)

    def test_bearish_fvg_in_zone(self):
        """Gap between c0.low=1.11 and c2.high=1.10 → bearish FVG inside CRT zone."""
        df = _df(
            _c(0, 1.12, 1.12, 1.11, 1.115),
            _c(1, 1.115, 1.115, 1.08, 1.09),  # impulse down
            _c(2, 1.10, 1.10, 1.08, 1.085),   # c2.high=1.10 < c0.low=1.11 → gap
        )
        result = find_entry(_BEAR, df)
        assert result is not None
        assert result.entry_model == EntryModel.FVG


# ---------------------------------------------------------------------------
# Breaker Block
# ---------------------------------------------------------------------------

class TestBreakerBlock:
    def test_bullish_breaker(self):
        """
        Bearish OB formed at candle 0 (body 1.095–1.11).
        Candle 3 closes above OB high (1.115 > 1.11) → bearish OB becomes BULLISH Breaker.
        Breaker zone (1.095–1.11) overlaps CRT range (1.08–1.12).
        """
        df = _df(
            _c(0, 1.09, 1.115, 1.09, 1.11),  # OB: bullish body 1.09–1.11
            _c(1, 1.11, 1.11, 1.09, 1.095),  # bearish impulse 1
            _c(2, 1.095, 1.095, 1.07, 1.075),# bearish impulse 2, close=1.075 < OB low=1.09 → OB valid
            _c(3, 1.075, 1.12, 1.075, 1.115),# close=1.115 > OB high=1.11 → OB broken → BULLISH Breaker
        )
        result = find_entry(_BULL, df)
        assert result is not None
        assert result.entry_model == EntryModel.BREAKER_BLOCK

    def test_bearish_breaker(self):
        """
        Bullish OB (bearish candle) formed, then broken below OB low → BEARISH Breaker.
        """
        df = _df(
            _c(0, 1.11, 1.115, 1.095, 1.097),# OB: bearish body 1.095–1.11
            _c(1, 1.097, 1.11, 1.097, 1.105),# bullish impulse 1
            _c(2, 1.105, 1.125, 1.105, 1.12),# bullish impulse 2, close=1.12 > OB high=1.115 → OB valid
            _c(3, 1.12, 1.12, 1.085, 1.09),  # close=1.09 < OB low=1.095 → OB broken → BEARISH Breaker
        )
        result = find_entry(_BEAR, df)
        assert result is not None
        assert result.entry_model == EntryModel.BREAKER_BLOCK


# ---------------------------------------------------------------------------
# Turtle Soup Wick (TWS)
# ---------------------------------------------------------------------------

class TestTWS:
    def test_tws_bullish(self):
        """
        Swing low at candle 2. Candle 5 sweeps swing low by wick but closes back.
        Zone inside CRT range.
        """
        df = _df(
            # Establish a swing low at index 2 (need 2 bars each side)
            _c(0, 1.10, 1.11, 1.095, 1.10),
            _c(1, 1.10, 1.11, 1.095, 1.10),
            _c(2, 1.10, 1.11, 1.088, 1.10),  # swing low: low=1.088
            _c(3, 1.10, 1.11, 1.095, 1.10),
            _c(4, 1.10, 1.11, 1.095, 1.10),
            # TWS candle: wick below swing low, close back above
            _c(5, 1.10, 1.11, 1.085, 1.093), # low=1.085 < 1.088, close=1.093 > 1.088 ✓
        )
        result = find_entry(_BULL, df)
        assert result is not None
        assert result.entry_model == EntryModel.TURTLE_SOUP_WICK
        assert result.entry_zone_low == pytest.approx(1.088)

    def test_tws_bearish(self):
        """Swing high at candle 2. Candle 5 sweeps swing high by wick, closes back below."""
        df = _df(
            _c(0, 1.10, 1.108, 1.095, 1.10),
            _c(1, 1.10, 1.108, 1.095, 1.10),
            _c(2, 1.10, 1.115, 1.095, 1.10), # swing high: high=1.115
            _c(3, 1.10, 1.108, 1.095, 1.10),
            _c(4, 1.10, 1.108, 1.095, 1.10),
            _c(5, 1.10, 1.118, 1.095, 1.112),# high=1.118 > 1.115, close=1.112 < 1.115 ✓
        )
        result = find_entry(_BEAR, df)
        assert result is not None
        assert result.entry_model == EntryModel.TURTLE_SOUP_WICK


# ---------------------------------------------------------------------------
# Turtle Soup Body (TBS)
# ---------------------------------------------------------------------------

class TestTBS:
    def test_tbs_bullish(self):
        """
        Swing low at candle 2. Candle 5 body closes below swing low.
        Candle 6 recovers above swing low → TBS.
        """
        df = _df(
            _c(0, 1.10, 1.11, 1.095, 1.10),
            _c(1, 1.10, 1.11, 1.095, 1.10),
            _c(2, 1.10, 1.11, 1.088, 1.10),  # swing low: 1.088
            _c(3, 1.10, 1.11, 1.095, 1.10),
            _c(4, 1.10, 1.11, 1.095, 1.10),
            _c(5, 1.10, 1.10, 1.082, 1.084), # close=1.084 < swing.low=1.088 → body sweep
            _c(6, 1.084, 1.11, 1.084, 1.095),# close=1.095 > 1.088 → reversal ✓
        )
        result = find_entry(_BULL, df)
        assert result is not None
        assert result.entry_model == EntryModel.TURTLE_SOUP_BODY
        assert result.time == _T0 + timedelta(minutes=15 * 6)  # reversal candle

    def test_tbs_bearish(self):
        """Swing high at candle 2. Body sweeps above, next candle reverses below."""
        df = _df(
            _c(0, 1.10, 1.108, 1.095, 1.10),
            _c(1, 1.10, 1.108, 1.095, 1.10),
            _c(2, 1.10, 1.115, 1.095, 1.10), # swing high: 1.115
            _c(3, 1.10, 1.108, 1.095, 1.10),
            _c(4, 1.10, 1.108, 1.095, 1.10),
            _c(5, 1.10, 1.12, 1.10, 1.118),  # close=1.118 > 1.115 → body sweep
            _c(6, 1.118, 1.118, 1.10, 1.112),# close=1.112 < 1.115 → reversal ✓
        )
        result = find_entry(_BEAR, df)
        assert result is not None
        assert result.entry_model == EntryModel.TURTLE_SOUP_BODY


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_no_entry_outside_zone(self):
        """Valid M15 OB but completely outside the CRT zone → None."""
        # CRT zone 1.08–1.12; OB at 1.04–1.06 (below zone)
        outside = _confluence(Direction.BULLISH, crt_hi=1.12, crt_lo=1.08)
        df = _df(
            _c(0, 1.06, 1.065, 1.04, 1.045),  # bearish OB outside zone
            _c(1, 1.045, 1.06, 1.045, 1.055),
            _c(2, 1.055, 1.07, 1.055, 1.068),  # close > OB high ✓ but zone is 1.04–1.06
        )
        assert find_entry(outside, df) is None

    def test_returns_none_when_no_trigger(self):
        """Flat M15 candles with no pattern → None."""
        df = _df(
            _c(0, 1.10, 1.11, 1.09, 1.10),
            _c(1, 1.10, 1.11, 1.09, 1.10),
            _c(2, 1.10, 1.11, 1.09, 1.10),
        )
        assert find_entry(_BULL, df) is None

    def test_priority_higher_model_wins(self):
        """
        _best() selects highest ENTRY_PRIORITY on same timestamp.
        TWS (4) must beat OB (1) when both are detected at the same candle time.
        We verify this by constructing two EntrySignals manually and checking _best().
        """
        from core.entry_models import _best
        from core.models import ENTRY_PRIORITY

        t = _T0 + timedelta(minutes=60)
        ob_entry = EntrySignal(
            confluence=_BULL, entry_model=EntryModel.ORDER_BLOCK,
            entry_zone_low=1.09, entry_zone_high=1.10, time=t, pair=PAIR,
        )
        tws_entry = EntrySignal(
            confluence=_BULL, entry_model=EntryModel.TURTLE_SOUP_WICK,
            entry_zone_low=1.09, entry_zone_high=1.10, time=t, pair=PAIR,
        )
        winner = _best([ob_entry, tws_entry])
        assert winner.entry_model == EntryModel.TURTLE_SOUP_WICK
        assert ENTRY_PRIORITY[EntryModel.TURTLE_SOUP_WICK] > ENTRY_PRIORITY[EntryModel.ORDER_BLOCK]
