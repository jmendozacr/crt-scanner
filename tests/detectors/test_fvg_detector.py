"""Tests for scanner.detectors.fvg_detector — SC-DET-FVG-1 through SC-DET-FVG-8."""
from __future__ import annotations

import pytest

from scanner.detectors._common import Bias
from scanner.detectors.fvg_detector import FVGResult, detect_fvg

from tests.detectors.conftest import load_fixture, make_candle

WIN_START = "2024-01-15 08:00"
WIN_END = "2024-01-15 12:00"
WIDE_START = "2000-01-01 00:00"
WIDE_END = "2099-12-31 23:59"


# ---------------------------------------------------------------------------
# SC-DET-FVG-1: Bullish FVG detected (c1.high < c3.low, strict)
# ---------------------------------------------------------------------------


class TestSCDETFVG1BullishFVG:
    def _candles(self) -> list:
        c1 = make_candle("2024-01-15 08:00:00", open=1.10000, high=1.10050, low=1.09900, close=1.10020)
        c2 = make_candle("2024-01-15 08:15:00", open=1.10020, high=1.10150, low=1.10000, close=1.10100)
        c3 = make_candle("2024-01-15 08:30:00", open=1.10100, high=1.10200, low=1.10100, close=1.10180)
        live = make_candle("2024-01-15 08:45:00")
        return [c1, c2, c3, live]

    def test_returns_result(self) -> None:
        result = detect_fvg(self._candles(), Bias.BULLISH, WIN_START, WIN_END)
        assert result is not None

    def test_bias_is_bullish(self) -> None:
        result = detect_fvg(self._candles(), Bias.BULLISH, WIN_START, WIN_END)
        assert result is not None
        assert result.bias is Bias.BULLISH

    def test_gap_low_is_c1_high(self) -> None:
        candles = self._candles()
        c1 = candles[0]
        result = detect_fvg(candles, Bias.BULLISH, WIN_START, WIN_END)
        assert result is not None
        assert result.gap_low == c1.high

    def test_gap_high_is_c3_low(self) -> None:
        candles = self._candles()
        c3 = candles[2]
        result = detect_fvg(candles, Bias.BULLISH, WIN_START, WIN_END)
        assert result is not None
        assert result.gap_high == c3.low

    def test_candle_1_datetime(self) -> None:
        candles = self._candles()
        c1 = candles[0]
        result = detect_fvg(candles, Bias.BULLISH, WIN_START, WIN_END)
        assert result is not None
        assert result.candle_1_datetime == c1.datetime


# ---------------------------------------------------------------------------
# SC-DET-FVG-2: Bearish FVG detected (c1.low > c3.high, strict)
# ---------------------------------------------------------------------------


class TestSCDETFVG2BearishFVG:
    def _candles(self) -> list:
        c1 = make_candle("2024-01-15 08:00:00", open=1.10200, high=1.10250, low=1.10150, close=1.10180)
        c2 = make_candle("2024-01-15 08:15:00", open=1.10180, high=1.10200, low=1.10050, close=1.10100)
        c3 = make_candle("2024-01-15 08:30:00", open=1.10100, high=1.10100, low=1.09900, close=1.09950)
        live = make_candle("2024-01-15 08:45:00")
        return [c1, c2, c3, live]

    def test_bias_is_bearish(self) -> None:
        result = detect_fvg(self._candles(), Bias.BEARISH, WIN_START, WIN_END)
        assert result is not None
        assert result.bias is Bias.BEARISH

    def test_gap_high_is_c1_low(self) -> None:
        candles = self._candles()
        c1 = candles[0]
        result = detect_fvg(candles, Bias.BEARISH, WIN_START, WIN_END)
        assert result is not None
        assert result.gap_high == c1.low

    def test_gap_low_is_c3_high(self) -> None:
        candles = self._candles()
        c3 = candles[2]
        result = detect_fvg(candles, Bias.BEARISH, WIN_START, WIN_END)
        assert result is not None
        assert result.gap_low == c3.high


# ---------------------------------------------------------------------------
# SC-DET-FVG-3: FVG triplet starts outside window → None
# ---------------------------------------------------------------------------


class TestSCDETFVG3OutsideWindow:
    def test_returns_none_when_c1_before_window(self) -> None:
        c1 = make_candle("2024-01-15 07:59:59", open=1.10000, high=1.10050, low=1.09900, close=1.10020)
        c2 = make_candle("2024-01-15 08:00:00", open=1.10020, high=1.10150, low=1.10000, close=1.10100)
        c3 = make_candle("2024-01-15 08:15:00", open=1.10100, high=1.10200, low=1.10100, close=1.10180)
        live = make_candle("2024-01-15 08:30:00")
        result = detect_fvg([c1, c2, c3, live], Bias.BULLISH, WIN_START, WIN_END)
        assert result is None


# ---------------------------------------------------------------------------
# SC-DET-FVG-4: Multiple FVGs → first (oldest) is returned
# ---------------------------------------------------------------------------


class TestSCDETFVG4MultipleFirstReturned:
    def test_returns_first_fvg(self) -> None:
        a1 = make_candle("2024-01-15 08:00:00", open=1.10000, high=1.10050, low=1.09900, close=1.10020)
        a2 = make_candle("2024-01-15 08:15:00", open=1.10020, high=1.10150, low=1.10000, close=1.10100)
        a3 = make_candle("2024-01-15 08:30:00", open=1.10100, high=1.10200, low=1.10100, close=1.10180)
        b1 = make_candle("2024-01-15 08:45:00", open=1.10180, high=1.10250, low=1.10180, close=1.10220)
        b2 = make_candle("2024-01-15 09:00:00", open=1.10220, high=1.10350, low=1.10200, close=1.10300)
        b3 = make_candle("2024-01-15 09:15:00", open=1.10300, high=1.10400, low=1.10300, close=1.10380)
        live = make_candle("2024-01-15 09:30:00")
        result = detect_fvg([a1, a2, a3, b1, b2, b3, live], Bias.BULLISH, WIN_START, WIN_END)
        assert result is not None
        assert result.candle_1_datetime == a1.datetime


# ---------------------------------------------------------------------------
# SC-DET-FVG-5: Touching candles (c1.high == c3.low) → None
# ---------------------------------------------------------------------------


class TestSCDETFVG5Touching:
    def test_returns_none_when_candles_touch(self) -> None:
        # c1.high == c3.low: strict condition (c1.high < c3.low) fails
        c1 = make_candle("2024-01-15 08:00:00", open=1.10000, high=1.10100, low=1.09900, close=1.10020)
        c2 = make_candle("2024-01-15 08:15:00", open=1.10020, high=1.10150, low=1.10000, close=1.10100)
        c3 = make_candle("2024-01-15 08:30:00", open=1.10100, high=1.10200, low=1.10100, close=1.10180)
        live = make_candle("2024-01-15 08:45:00")
        result = detect_fvg([c1, c2, c3, live], Bias.BULLISH, WIN_START, WIN_END)
        assert result is None


# ---------------------------------------------------------------------------
# SC-DET-FVG-6: Fewer than 3 closed candles → None
# ---------------------------------------------------------------------------


class TestSCDETFVG6FewerThan3Closed:
    def test_returns_none_with_two_total_candles(self) -> None:
        c1 = make_candle("2024-01-15 08:00:00")
        live = make_candle("2024-01-15 08:15:00")
        result = detect_fvg([c1, live], Bias.BULLISH, WIN_START, WIN_END)
        assert result is None

    def test_returns_none_with_only_live_candle(self) -> None:
        live = make_candle("2024-01-15 08:00:00")
        result = detect_fvg([live], Bias.BULLISH, WIN_START, WIN_END)
        assert result is None


# ---------------------------------------------------------------------------
# SC-DET-FVG-7: midpoint == (gap_high + gap_low) / 2
# ---------------------------------------------------------------------------


class TestSCDETFVG7Midpoint:
    def test_midpoint_is_average_of_gap_boundaries(self) -> None:
        c1 = make_candle("2024-01-15 08:00:00", open=1.10000, high=1.10050, low=1.09900, close=1.10020)
        c2 = make_candle("2024-01-15 08:15:00", open=1.10020, high=1.10150, low=1.10000, close=1.10100)
        c3 = make_candle("2024-01-15 08:30:00", open=1.10100, high=1.10200, low=1.10100, close=1.10180)
        live = make_candle("2024-01-15 08:45:00")
        result = detect_fvg([c1, c2, c3, live], Bias.BULLISH, WIN_START, WIN_END)
        assert result is not None
        assert result.midpoint == pytest.approx((result.gap_high + result.gap_low) / 2)

    def test_midpoint_is_between_gap_boundaries(self) -> None:
        c1 = make_candle("2024-01-15 08:00:00", open=1.10000, high=1.10050, low=1.09900, close=1.10020)
        c2 = make_candle("2024-01-15 08:15:00", open=1.10020, high=1.10150, low=1.10000, close=1.10100)
        c3 = make_candle("2024-01-15 08:30:00", open=1.10100, high=1.10200, low=1.10100, close=1.10180)
        live = make_candle("2024-01-15 08:45:00")
        result = detect_fvg([c1, c2, c3, live], Bias.BULLISH, WIN_START, WIN_END)
        assert result is not None
        assert result.gap_low <= result.midpoint <= result.gap_high


# ---------------------------------------------------------------------------
# SC-DET-FVG-8: Smoke test with real EUR/USD M15 fixture
# ---------------------------------------------------------------------------


class TestSCDETFVG8Smoke:
    def test_smoke_eurusd_15min_bullish(self) -> None:
        candles = load_fixture("EUR/USD", "15min")
        result = detect_fvg(candles, Bias.BULLISH, WIDE_START, WIDE_END)
        assert result is None or isinstance(result, FVGResult)
        if result is not None:
            assert result.gap_high > result.gap_low
            assert result.gap_low <= result.midpoint <= result.gap_high

    def test_smoke_eurusd_15min_bearish(self) -> None:
        candles = load_fixture("EUR/USD", "15min")
        result = detect_fvg(candles, Bias.BEARISH, WIDE_START, WIDE_END)
        assert result is None or isinstance(result, FVGResult)
        if result is not None:
            assert result.gap_high > result.gap_low
