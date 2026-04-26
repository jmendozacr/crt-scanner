"""Tests for scanner.detectors._common — SC-DET-CMN-1 through SC-DET-CMN-13."""
from __future__ import annotations

import pytest

from scanner.detectors._common import Bias, exclude_live, find_previous_swing, in_window, is_doji

from tests.detectors.conftest import make_bearish, make_bullish, make_candle, make_doji


# ---------------------------------------------------------------------------
# SC-DET-CMN-1: Bias enum values
# ---------------------------------------------------------------------------


class TestSCDETCMN1BiasEnum:
    def test_bullish_value(self) -> None:
        assert Bias.BULLISH == "bullish"

    def test_bearish_value(self) -> None:
        assert Bias.BEARISH == "bearish"

    def test_is_str_subclass(self) -> None:
        assert isinstance(Bias.BULLISH, str)


# ---------------------------------------------------------------------------
# SC-DET-CMN-2,3,4: exclude_live
# ---------------------------------------------------------------------------


class TestSCDETCMN234ExcludeLive:
    def test_removes_last_candle(self) -> None:
        candles = [make_candle(datetime=f"2024-01-0{i} 00:00:00") for i in range(1, 5)]
        result = exclude_live(candles)
        assert len(result) == 3
        assert result[-1].datetime == "2024-01-03 00:00:00"

    def test_single_candle_returns_empty(self) -> None:
        candles = [make_candle()]
        assert exclude_live(candles) == []

    def test_empty_list_returns_empty(self) -> None:
        assert exclude_live([]) == []

    def test_does_not_mutate_original(self) -> None:
        candles = [make_candle(datetime=f"2024-01-0{i} 00:00:00") for i in range(1, 4)]
        _ = exclude_live(candles)
        assert len(candles) == 3


# ---------------------------------------------------------------------------
# SC-DET-CMN-5,6,7,8: in_window
# ---------------------------------------------------------------------------


class TestSCDETCMN5678InWindow:
    def test_dt_at_start_is_inside(self) -> None:
        assert in_window("2024-01-15 08:00:00", "2024-01-15 08:00:00", "2024-01-15 12:00:00")

    def test_dt_before_start_is_outside(self) -> None:
        assert not in_window("2024-01-15 07:59:59", "2024-01-15 08:00:00", "2024-01-15 12:00:00")

    def test_dt_at_end_is_outside(self) -> None:
        assert not in_window("2024-01-15 12:00:00", "2024-01-15 08:00:00", "2024-01-15 12:00:00")

    def test_dt_inside_interval(self) -> None:
        assert in_window("2024-01-15 10:00:00", "2024-01-15 08:00:00", "2024-01-15 12:00:00")


# ---------------------------------------------------------------------------
# SC-DET-CMN-9,10: is_doji
# ---------------------------------------------------------------------------


class TestSCDETCMN910IsDoji:
    def test_doji_when_open_equals_close(self) -> None:
        candle = make_doji()
        assert is_doji(candle)

    def test_not_doji_when_open_differs_close(self) -> None:
        candle = make_bullish()
        assert not is_doji(candle)


# ---------------------------------------------------------------------------
# SC-DET-CMN-11,12: find_previous_swing (successful detection)
# ---------------------------------------------------------------------------


class TestSCDETCMN1112FindPreviousSwing:
    def _make_bullish_swing_candles(self) -> list:
        # Index 0: high candle, index 1: LOW fractal, index 2: high candle, index 3: anchor
        # fractal at index 1: low < index 0 AND low < index 2
        c0 = make_candle(datetime="2024-01-10 00:00:00", low=1.10000, high=1.10100, open=1.10050, close=1.10080)
        c1 = make_candle(datetime="2024-01-11 00:00:00", low=1.09800, high=1.10000, open=1.09900, close=1.09950)
        c2 = make_candle(datetime="2024-01-12 00:00:00", low=1.10000, high=1.10200, open=1.10050, close=1.10150)
        c3 = make_candle(datetime="2024-01-13 00:00:00", low=1.10050, high=1.10300, open=1.10100, close=1.10250)
        return [c0, c1, c2, c3]

    def _make_bearish_swing_candles(self) -> list:
        # fractal at index 1: high > index 0 AND high > index 2
        c0 = make_candle(datetime="2024-01-10 00:00:00", low=1.10000, high=1.10100, open=1.10050, close=1.10080)
        c1 = make_candle(datetime="2024-01-11 00:00:00", low=1.10000, high=1.10300, open=1.10200, close=1.10050)
        c2 = make_candle(datetime="2024-01-12 00:00:00", low=1.10000, high=1.10100, open=1.10050, close=1.10080)
        c3 = make_candle(datetime="2024-01-13 00:00:00", low=1.09800, high=1.10050, open=1.10000, close=1.09850)
        return [c0, c1, c2, c3]

    def test_finds_bullish_swing_low(self) -> None:
        candles = self._make_bullish_swing_candles()
        result = find_previous_swing(candles, side=Bias.BULLISH, anchor_index=3)
        assert result is not None
        assert result.datetime == "2024-01-11 00:00:00"

    def test_finds_bearish_swing_high(self) -> None:
        candles = self._make_bearish_swing_candles()
        result = find_previous_swing(candles, side=Bias.BEARISH, anchor_index=3)
        assert result is not None
        assert result.datetime == "2024-01-11 00:00:00"


# ---------------------------------------------------------------------------
# SC-DET-CMN-13: find_previous_swing returns None when insufficient fractals
# ---------------------------------------------------------------------------


class TestSCDETCMN13FindPreviousSwingInsufficient:
    def test_returns_none_when_no_fractal(self) -> None:
        # Monotonically increasing lows — no bullish fractal exists
        c0 = make_candle(datetime="2024-01-10 00:00:00", low=1.09800, high=1.10100, open=1.09900, close=1.10080)
        c1 = make_candle(datetime="2024-01-11 00:00:00", low=1.09900, high=1.10200, open=1.10000, close=1.10150)
        c2 = make_candle(datetime="2024-01-12 00:00:00", low=1.10000, high=1.10300, open=1.10050, close=1.10250)
        candles = [c0, c1, c2]
        result = find_previous_swing(candles, side=Bias.BULLISH, anchor_index=2)
        assert result is None
