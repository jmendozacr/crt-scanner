"""Tests for scanner.detectors.turtle_body_soup — SC-TBS-1..6."""
from __future__ import annotations

import pytest

from scanner.data.candle import Candle
from scanner.detectors._common import Bias
from scanner.detectors.turtle_body_soup import TBSResult, detect_tbs

from tests.detectors.conftest import make_candle, make_bullish, make_bearish


def _make_bullish_fractal(base_dt_hour: int) -> list[Candle]:
    """Create a 3-candle sequence where the middle is a bullish fractal swing low."""
    prev = make_candle(
        datetime=f"2024-01-15 {base_dt_hour:02d}:00:00",
        open=1.10000, high=1.10100, low=1.09900, close=1.10050,
    )
    curr = make_candle(
        datetime=f"2024-01-15 {base_dt_hour + 1:02d}:00:00",
        open=1.10050, high=1.10080, low=1.09800, close=1.10060,
    )
    nxt = make_candle(
        datetime=f"2024-01-15 {base_dt_hour + 2:02d}:00:00",
        open=1.10060, high=1.10120, low=1.09850, close=1.10100,
    )
    return [prev, curr, nxt]


def _make_bearish_fractal(base_dt_hour: int) -> list[Candle]:
    """Create a 3-candle sequence where the middle is a bearish fractal swing high."""
    prev = make_candle(
        datetime=f"2024-01-15 {base_dt_hour:02d}:00:00",
        open=1.10050, high=1.10120, low=1.09950, close=1.10020,
    )
    curr = make_candle(
        datetime=f"2024-01-15 {base_dt_hour + 1:02d}:00:00",
        open=1.10020, high=1.10200, low=1.09970, close=1.10010,
    )
    nxt = make_candle(
        datetime=f"2024-01-15 {base_dt_hour + 2:02d}:00:00",
        open=1.10010, high=1.10150, low=1.09960, close=1.10000,
    )
    return [prev, curr, nxt]


# SC-TBS-1: BULLISH TBS detected
class TestSCTBS1BullishDetected:
    def test_bullish_tbs_returns_result(self) -> None:
        # Setup: fractal swing low at [08:00-10:00], sweep candle in window
        fractal = _make_bullish_fractal(8)
        # fractal[1] = swing low (low=1.09800, body_low = min(open,close) = min(1.10050,1.10060) = 1.10050)
        # We need a candle that sweeps body_low of the swing
        # swing.open=1.10050, swing.close=1.10060 → body_low = 1.10050
        swing_candle = fractal[1]
        body_low = min(swing_candle.open, swing_candle.close)

        sweep = make_candle(
            datetime="2024-01-15 09:15:00",
            open=1.10020,
            high=1.10080,
            low=body_low - 0.00050,   # below body_low
            close=body_low + 0.00010,  # close above body_low (bullish)
        )
        live = make_candle(datetime="2024-01-15 09:30:00")  # excluded

        candles = fractal + [sweep, live]
        result = detect_tbs(
            candles,
            htf_bias=Bias.BULLISH,
            window_start="2024-01-15 09:00",
            window_end="2024-01-15 13:00",
        )
        assert result is not None
        assert result.bias is Bias.BULLISH
        assert result.swept_body_level == pytest.approx(body_low)
        assert result.tbs_candle_datetime == sweep.datetime


# SC-TBS-2: BEARISH TBS detected
class TestSCTBS2BearishDetected:
    def test_bearish_tbs_returns_result(self) -> None:
        fractal = _make_bearish_fractal(8)
        swing_candle = fractal[1]
        body_high = max(swing_candle.open, swing_candle.close)

        sweep = make_candle(
            datetime="2024-01-15 09:15:00",
            open=1.10080,
            high=body_high + 0.00050,   # above body_high
            low=1.10020,
            close=body_high - 0.00010,   # close below body_high (bearish)
        )
        live = make_candle(datetime="2024-01-15 09:30:00")

        candles = fractal + [sweep, live]
        result = detect_tbs(
            candles,
            htf_bias=Bias.BEARISH,
            window_start="2024-01-15 09:00",
            window_end="2024-01-15 13:00",
        )
        assert result is not None
        assert result.bias is Bias.BEARISH
        assert result.swept_body_level == pytest.approx(body_high)
        assert result.tbs_candle_datetime == sweep.datetime


# SC-TBS-3: returns None when fewer than 3 candles in window
class TestSCTBS3TooFewCandles:
    def test_returns_none_with_few_candles(self) -> None:
        c1 = make_candle(datetime="2024-01-15 09:00:00")
        c2 = make_candle(datetime="2024-01-15 09:15:00")
        live = make_candle(datetime="2024-01-15 09:30:00")
        result = detect_tbs(
            [c1, c2, live],
            htf_bias=Bias.BULLISH,
            window_start="2024-01-15 09:00",
            window_end="2024-01-15 13:00",
        )
        assert result is None


# SC-TBS-4: candles outside window are ignored
class TestSCTBS4WindowBoundary:
    def test_candles_outside_window_ignored(self) -> None:
        # All closed candles are before the window
        before = [
            make_candle(datetime=f"2024-01-15 0{h}:00:00")
            for h in range(5, 9)
        ]
        live = make_candle(datetime="2024-01-15 10:00:00")
        result = detect_tbs(
            before + [live],
            htf_bias=Bias.BULLISH,
            window_start="2024-01-15 09:00",
            window_end="2024-01-15 13:00",
        )
        assert result is None


# SC-TBS-5: close must be above body_low for bullish (no partial sweeps that don't close back)
# Fractal is placed BEFORE the window so only the failed sweep candles are inside.
class TestSCTBS5CloseNotAboveBodyLow:
    def test_returns_none_when_close_below_body_low(self) -> None:
        # Fractal entirely before window (hours 5, 6, 7) so they serve as prior context only
        fractal = _make_bullish_fractal(5)
        swing_candle = fractal[1]  # 06:00 — the fractal low
        body_low = min(swing_candle.open, swing_candle.close)

        # Three candles inside the window so we pass the len >= 3 guard;
        # neutral candles have lows ABOVE body_low so they cannot trigger TBS
        neutral = make_candle(
            datetime="2024-01-15 09:00:00",
            open=1.10060, high=1.10080, low=1.10055, close=1.10070,
        )
        neutral2 = make_candle(
            datetime="2024-01-15 09:15:00",
            open=1.10065, high=1.10075, low=1.10058, close=1.10068,
        )
        # Failed sweep: low pierces body_low but close does NOT recover
        failed_sweep = make_candle(
            datetime="2024-01-15 09:30:00",
            open=1.10020,
            high=1.10080,
            low=body_low - 0.00050,
            close=body_low - 0.00010,  # close remains below body_low
        )
        live = make_candle(datetime="2024-01-15 09:45:00")

        candles = fractal + [neutral, neutral2, failed_sweep, live]
        result = detect_tbs(
            candles,
            htf_bias=Bias.BULLISH,
            window_start="2024-01-15 09:00",
            window_end="2024-01-15 13:00",
        )
        assert result is None


# SC-TBS-5 (spec): no swing found → None
# (all candles in window have monotonically increasing lows — no fractal low exists)
class TestSCTBS5NoSwingFound:
    def test_returns_none_when_no_swing(self) -> None:
        # Monotonically increasing lows: no fractal low can be identified
        candles = [
            make_candle(datetime=f"2024-01-15 09:{m:02d}:00", low=1.09800 + m * 0.00010)
            for m in range(6)
        ]
        # Add a live candle at the end
        live = make_candle(datetime="2024-01-15 09:45:00", low=1.09860)
        result = detect_tbs(
            candles + [live],
            htf_bias=Bias.BULLISH,
            window_start="2024-01-15 09:00",
            window_end="2024-01-15 13:00",
        )
        assert result is None


# SC-TBS-6: TBSResult fields are correct
class TestSCTBS6FieldValues:
    def test_result_fields(self) -> None:
        fractal = _make_bullish_fractal(8)
        swing_candle = fractal[1]
        body_low = min(swing_candle.open, swing_candle.close)

        sweep = make_candle(
            datetime="2024-01-15 09:15:00",
            open=1.10020,
            high=1.10080,
            low=body_low - 0.00050,
            close=body_low + 0.00010,
        )
        live = make_candle(datetime="2024-01-15 09:30:00")

        candles = fractal + [sweep, live]
        result = detect_tbs(
            candles,
            htf_bias=Bias.BULLISH,
            window_start="2024-01-15 09:00",
            window_end="2024-01-15 13:00",
        )
        assert result is not None
        assert result.bias is Bias.BULLISH
        assert result.swept_swing_datetime == swing_candle.datetime
        assert result.tbs_candle_datetime == sweep.datetime
        assert result.window_start == "2024-01-15 09:00"
        assert result.window_end_hint == ""
