"""Tests for scanner.detectors.model1_detector — SC-M1-1..6."""
from __future__ import annotations

import pytest

from scanner.data.candle import Candle
from scanner.detectors._common import Bias
from scanner.detectors.model1_detector import MIN_BODY_RATIO, Model1Result, detect_model1

from tests.detectors.conftest import make_candle, make_bullish, make_bearish


# Helpers — synthetic candles with controlled body ratios

def _thick_bearish(datetime: str, open: float = 1.10100) -> Candle:
    """A thick bearish candle: body ratio > 0.5, close < open (counter to bullish bias)."""
    # range = 0.00200, body = 0.00150 → ratio = 0.75
    return make_candle(
        datetime=datetime,
        open=open,
        high=open + 0.00050,
        low=open - 0.00150,
        close=open - 0.00150,
    )


def _thick_bullish(datetime: str, open: float = 1.09950) -> Candle:
    """A thick bullish candle: body ratio > 0.5, close > open (counter to bearish bias)."""
    return make_candle(
        datetime=datetime,
        open=open,
        high=open + 0.00150,
        low=open - 0.00050,
        close=open + 0.00150,
    )


def _thin_candle(datetime: str, open: float = 1.10050) -> Candle:
    """A candle with body_ratio < MIN_BODY_RATIO (doji-like)."""
    # range = 0.00200, body = 0.00050 → ratio = 0.25
    return make_candle(
        datetime=datetime,
        open=open,
        high=open + 0.00100,
        low=open - 0.00100,
        close=open + 0.00050,
    )


# SC-M1-1: BULLISH Model #1 detected
class TestSCM11BullishDetected:
    def test_bullish_model1_returns_result(self) -> None:
        tbs_dt = "2024-01-15 09:00:00"
        window_end = "2024-01-15 13:00"

        # Thick counter-directional (bearish) candle after TBS
        m1 = _thick_bearish(datetime="2024-01-15 09:15:00", open=1.10100)
        # Entry confirmation: close above m1.open (1.10100)
        confirm = make_candle(
            datetime="2024-01-15 09:30:00",
            open=1.10050,
            high=1.10200,
            low=1.10000,
            close=1.10150,  # > m1.open
        )
        live = make_candle(datetime="2024-01-15 09:45:00")

        candles = [make_candle(datetime="2024-01-15 08:45:00"), m1, confirm, live]
        result = detect_model1(candles, Bias.BULLISH, tbs_dt, window_end)

        assert result is not None
        assert result.bias is Bias.BULLISH
        assert result.model1_candle_datetime == m1.datetime
        assert result.entry_candle_datetime == confirm.datetime
        assert result.entry_price == pytest.approx(m1.open)


# SC-M1-2: BEARISH Model #1 detected
class TestSCM12BearishDetected:
    def test_bearish_model1_returns_result(self) -> None:
        tbs_dt = "2024-01-15 09:00:00"
        window_end = "2024-01-15 13:00"

        m1 = _thick_bullish(datetime="2024-01-15 09:15:00", open=1.09950)
        # Entry: close below m1.open (1.09950)
        confirm = make_candle(
            datetime="2024-01-15 09:30:00",
            open=1.10000,
            high=1.10050,
            low=1.09850,
            close=1.09900,  # < m1.open
        )
        live = make_candle(datetime="2024-01-15 09:45:00")

        candles = [make_candle(datetime="2024-01-15 08:45:00"), m1, confirm, live]
        result = detect_model1(candles, Bias.BEARISH, tbs_dt, window_end)

        assert result is not None
        assert result.bias is Bias.BEARISH
        assert result.entry_price == pytest.approx(m1.open)


# SC-M1-3: returns None when no thick counter-directional candle
class TestSCM13NoThickCandle:
    def test_returns_none_no_thick_candle(self) -> None:
        tbs_dt = "2024-01-15 09:00:00"
        window_end = "2024-01-15 13:00"

        thin = _thin_candle(datetime="2024-01-15 09:15:00")
        live = make_candle(datetime="2024-01-15 09:30:00")

        candles = [make_candle(datetime="2024-01-15 08:45:00"), thin, live]
        result = detect_model1(candles, Bias.BULLISH, tbs_dt, window_end)
        assert result is None


# SC-M1-4: returns None when no confirmation after Model #1
class TestSCM14NoConfirmation:
    def test_returns_none_no_confirmation(self) -> None:
        tbs_dt = "2024-01-15 09:00:00"
        window_end = "2024-01-15 13:00"

        m1 = _thick_bearish(datetime="2024-01-15 09:15:00", open=1.10100)
        # confirm closes BELOW m1.open — not a valid confirmation
        bad_confirm = make_candle(
            datetime="2024-01-15 09:30:00",
            open=1.10050,
            high=1.10080,
            low=1.09980,
            close=1.10000,  # <= m1.open, no confirmation for BULLISH
        )
        live = make_candle(datetime="2024-01-15 09:45:00")

        candles = [make_candle(datetime="2024-01-15 08:45:00"), m1, bad_confirm, live]
        result = detect_model1(candles, Bias.BULLISH, tbs_dt, window_end)
        assert result is None


# SC-M1-5: candles before or at tbs_dt are ignored
class TestSCM15TBSWindowFilter:
    def test_candles_at_or_before_tbs_ignored(self) -> None:
        tbs_dt = "2024-01-15 09:15:00"
        window_end = "2024-01-15 13:00"

        # This candle is AT tbs_dt — should be ignored (strictly after)
        at_tbs = _thick_bearish(datetime="2024-01-15 09:15:00", open=1.10100)
        live = make_candle(datetime="2024-01-15 09:30:00")

        candles = [make_candle(datetime="2024-01-15 08:45:00"), at_tbs, live]
        result = detect_model1(candles, Bias.BULLISH, tbs_dt, window_end)
        assert result is None


# SC-M1-6 (window_end boundary): candles at or after window_end are ignored
class TestSCM16WindowEndFilter:
    def test_candles_at_or_after_window_end_ignored(self) -> None:
        tbs_dt = "2024-01-15 09:00:00"
        window_end = "2024-01-15 09:15"  # tight window

        # This thick candle is at window_end — excluded (half-open interval)
        m1 = _thick_bearish(datetime="2024-01-15 09:15:00", open=1.10100)
        live = make_candle(datetime="2024-01-15 09:30:00")

        candles = [make_candle(datetime="2024-01-15 08:45:00"), m1, live]
        result = detect_model1(candles, Bias.BULLISH, tbs_dt, window_end)
        assert result is None


# SC-M1-6 (spec): doji (high == low) is skipped, next thick candle is used
class TestSCM1DojiSkipped:
    def test_doji_skipped_uses_next_thick_candle(self) -> None:
        tbs_dt = "2024-01-15 09:00:00"
        window_end = "2024-01-15 13:00"

        # Doji: high == low — body_ratio computation must be skipped (no ZeroDivisionError)
        doji = make_candle(
            datetime="2024-01-15 09:15:00",
            open=1.10200,
            high=1.10200,
            low=1.10200,
            close=1.10200,
        )
        # Second candidate: thick bearish (counter to BULLISH bias)
        m1 = _thick_bearish(datetime="2024-01-15 09:30:00", open=1.10100)
        # Confirmation candle: close above m1.open
        confirm = make_candle(
            datetime="2024-01-15 09:45:00",
            open=1.10050,
            high=1.10200,
            low=1.10000,
            close=1.10150,  # > m1.open (1.10100)
        )
        live = make_candle(datetime="2024-01-15 10:00:00")

        candles = [make_candle(datetime="2024-01-15 08:45:00"), doji, m1, confirm, live]
        result = detect_model1(candles, Bias.BULLISH, tbs_dt, window_end)

        assert result is not None, "Doji must be skipped without error; next thick candle must be used"
        assert result.model1_candle_datetime == m1.datetime
        assert result.entry_price == pytest.approx(m1.open)
        assert result.entry_candle_datetime == confirm.datetime
