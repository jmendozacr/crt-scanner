"""Tests for scanner.detectors.turtle_soup — SC-DET-TS-1 through SC-DET-TS-7."""
from __future__ import annotations

from scanner.detectors._common import Bias
from scanner.detectors.turtle_soup import TurtleSoupResult, detect_turtle_soup

from tests.detectors.conftest import load_fixture, make_candle


# ---------------------------------------------------------------------------
# Shared candle builders
# ---------------------------------------------------------------------------


def _bullish_candles() -> list:
    # fractal swing low at index 1 (swing_low.low < ref.low AND swing_low.low < recovery.low)
    # ts_candle sweeps the fractal low and closes bullish
    ref = make_candle("2024-01-15 04:00:00", open=1.10050, high=1.10200, low=1.10000, close=1.10150)
    swing_low = make_candle("2024-01-15 08:00:00", open=1.10000, high=1.10100, low=1.09800, close=1.09900)
    recovery = make_candle("2024-01-15 12:00:00", open=1.09900, high=1.10050, low=1.09950, close=1.10000)
    ts_candle = make_candle("2024-01-15 16:00:00", open=1.09800, high=1.10100, low=1.09700, close=1.09950)
    live = make_candle("2024-01-15 20:00:00")
    return [ref, swing_low, recovery, ts_candle, live]


def _bearish_candles() -> list:
    # fractal swing high at index 1; ts_candle sweeps it and closes bearish
    ref = make_candle("2024-01-15 04:00:00", open=1.10000, high=1.10100, low=1.09900, close=1.10050)
    swing_high = make_candle("2024-01-15 08:00:00", open=1.10050, high=1.10300, low=1.10000, close=1.10200)
    recovery = make_candle("2024-01-15 12:00:00", open=1.10200, high=1.10200, low=1.10000, close=1.10100)
    ts_candle = make_candle("2024-01-15 16:00:00", open=1.10200, high=1.10400, low=1.10050, close=1.10100)
    live = make_candle("2024-01-15 20:00:00")
    return [ref, swing_high, recovery, ts_candle, live]


# ---------------------------------------------------------------------------
# SC-DET-TS-1: Bullish Turtle Soup detected
# ---------------------------------------------------------------------------


class TestSCDETTS1BullishTS:
    def test_bias_is_bullish(self) -> None:
        result = detect_turtle_soup(_bullish_candles(), Bias.BULLISH)
        assert result is not None
        assert result.bias is Bias.BULLISH

    def test_swept_level_is_fractal_low(self) -> None:
        candles = _bullish_candles()
        swing_low = candles[1]
        result = detect_turtle_soup(candles, Bias.BULLISH)
        assert result is not None
        assert result.swept_level == swing_low.low

    def test_swept_datetime_is_fractal_candle(self) -> None:
        candles = _bullish_candles()
        swing_low = candles[1]
        result = detect_turtle_soup(candles, Bias.BULLISH)
        assert result is not None
        assert result.swept_datetime == swing_low.datetime

    def test_ts_candle_datetime_is_last_closed(self) -> None:
        candles = _bullish_candles()
        ts_candle = candles[-2]
        result = detect_turtle_soup(candles, Bias.BULLISH)
        assert result is not None
        assert result.ts_candle_datetime == ts_candle.datetime


# ---------------------------------------------------------------------------
# SC-DET-TS-2: Bearish Turtle Soup detected
# ---------------------------------------------------------------------------


class TestSCDETTS2BearishTS:
    def test_bias_is_bearish(self) -> None:
        result = detect_turtle_soup(_bearish_candles(), Bias.BEARISH)
        assert result is not None
        assert result.bias is Bias.BEARISH

    def test_swept_level_is_fractal_high(self) -> None:
        candles = _bearish_candles()
        swing_high = candles[1]
        result = detect_turtle_soup(candles, Bias.BEARISH)
        assert result is not None
        assert result.swept_level == swing_high.high

    def test_swept_datetime_is_fractal_candle(self) -> None:
        candles = _bearish_candles()
        swing_high = candles[1]
        result = detect_turtle_soup(candles, Bias.BEARISH)
        assert result is not None
        assert result.swept_datetime == swing_high.datetime


# ---------------------------------------------------------------------------
# SC-DET-TS-3: Sweep of low but bearish close → None (bias=BULLISH)
# ---------------------------------------------------------------------------


class TestSCDETTS3SweepNoClose:
    def test_returns_none_when_close_is_bearish(self) -> None:
        ref = make_candle("2024-01-15 04:00:00", open=1.10050, high=1.10200, low=1.10000, close=1.10150)
        swing_low = make_candle("2024-01-15 08:00:00", open=1.10000, high=1.10100, low=1.09800, close=1.09900)
        recovery = make_candle("2024-01-15 12:00:00", open=1.09900, high=1.10050, low=1.09950, close=1.10000)
        # sweeps swing_low.low but closes bearish (close < open)
        ts_wrong = make_candle("2024-01-15 16:00:00", open=1.09900, high=1.10100, low=1.09700, close=1.09750)
        live = make_candle("2024-01-15 20:00:00")
        result = detect_turtle_soup([ref, swing_low, recovery, ts_wrong, live], Bias.BULLISH)
        assert result is None


# ---------------------------------------------------------------------------
# SC-DET-TS-4: Sweep of high but bullish close → None (bias=BEARISH)
# ---------------------------------------------------------------------------


class TestSCDETTS4SweepHighNoClose:
    def test_returns_none_when_close_is_bullish(self) -> None:
        ref = make_candle("2024-01-15 04:00:00", open=1.10000, high=1.10100, low=1.09900, close=1.10050)
        swing_high = make_candle("2024-01-15 08:00:00", open=1.10050, high=1.10300, low=1.10000, close=1.10200)
        recovery = make_candle("2024-01-15 12:00:00", open=1.10200, high=1.10200, low=1.10000, close=1.10100)
        # sweeps swing_high.high but closes bullish (close > open)
        ts_wrong = make_candle("2024-01-15 16:00:00", open=1.10100, high=1.10400, low=1.09950, close=1.10250)
        live = make_candle("2024-01-15 20:00:00")
        result = detect_turtle_soup([ref, swing_high, recovery, ts_wrong, live], Bias.BEARISH)
        assert result is None


# ---------------------------------------------------------------------------
# SC-DET-TS-5: Fewer than 3 closed candles → None
# ---------------------------------------------------------------------------


class TestSCDETTS5FewerThan3Closed:
    def test_returns_none_with_two_total_candles(self) -> None:
        c1 = make_candle("2024-01-15 04:00:00")
        live = make_candle("2024-01-15 08:00:00")
        result = detect_turtle_soup([c1, live], Bias.BULLISH)
        assert result is None

    def test_returns_none_with_one_total_candle(self) -> None:
        live = make_candle("2024-01-15 04:00:00")
        result = detect_turtle_soup([live], Bias.BULLISH)
        assert result is None


# ---------------------------------------------------------------------------
# SC-DET-TS-6: window_start == ts_candle_datetime and window_end_hint == ""
# ---------------------------------------------------------------------------


class TestSCDETTS6WindowFields:
    def test_window_start_equals_ts_candle_datetime(self) -> None:
        candles = _bullish_candles()
        result = detect_turtle_soup(candles, Bias.BULLISH)
        assert result is not None
        assert result.window_start == result.ts_candle_datetime

    def test_window_end_hint_is_empty_string(self) -> None:
        candles = _bullish_candles()
        result = detect_turtle_soup(candles, Bias.BULLISH)
        assert result is not None
        assert result.window_end_hint == ""


# ---------------------------------------------------------------------------
# SC-DET-TS-7: Smoke test with real EUR/USD H4 fixture
# ---------------------------------------------------------------------------


class TestSCDETTS7Smoke:
    def test_smoke_eurusd_4h_bullish(self) -> None:
        candles = load_fixture("EUR/USD", "4h")
        result = detect_turtle_soup(candles, Bias.BULLISH)
        assert result is None or isinstance(result, TurtleSoupResult)

    def test_smoke_eurusd_4h_bearish(self) -> None:
        candles = load_fixture("EUR/USD", "4h")
        result = detect_turtle_soup(candles, Bias.BEARISH)
        assert result is None or isinstance(result, TurtleSoupResult)
