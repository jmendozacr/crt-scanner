"""Tests for scanner.detectors.crt_bias — SC-DET-CRT-1 through SC-DET-CRT-8."""
from __future__ import annotations

import pytest

from scanner.detectors._common import Bias
from scanner.detectors.crt_bias import CRTResult, _check_2candle, _check_3candle, detect_crt_bias

from tests.detectors.conftest import make_candle, make_doji


# ---------------------------------------------------------------------------
# SC-DET-CRT-1: 3-candle bullish pattern
# ---------------------------------------------------------------------------


class TestSCDETCRT13CandleBullish:
    def _candles(self) -> list:
        # c1: reference candle
        # c2: sweeps below c1.low (manipulation)
        # c3: closes above c2.open and c1.low (confirmation, bullish body)
        # To avoid 2-candle triggering on (c2, c3):
        #   2-candle bullish needs c3.low < c2.low → ensure c3.low > c2.low
        c1 = make_candle(datetime="2024-01-13 00:00:00", open=1.10050, high=1.10200, low=1.10000, close=1.10150)
        c2 = make_candle(datetime="2024-01-14 00:00:00", open=1.10100, high=1.10200, low=1.09800, close=1.09850)
        c3 = make_candle(datetime="2024-01-15 00:00:00", open=1.09900, high=1.10300, low=1.09950, close=1.10200)
        live = make_candle(datetime="2024-01-16 00:00:00")
        return [c1, c2, c3, live]

    def test_bias_is_bullish(self) -> None:
        result = detect_crt_bias({"1day": self._candles()})
        assert result is not None
        assert result.bias is Bias.BULLISH

    def test_pattern_is_3candle(self) -> None:
        result = detect_crt_bias({"1day": self._candles()})
        assert result is not None
        assert result.pattern == "3-candle"

    def test_tp_level_is_max_c1_c2_high(self) -> None:
        candles = self._candles()
        closed = candles[:-1]
        c1, c2 = closed[-3], closed[-2]
        result = detect_crt_bias({"1day": candles})
        assert result is not None
        assert result.tp_level == max(c1.high, c2.high)

    def test_sweep_level_is_c2_low(self) -> None:
        candles = self._candles()
        closed = candles[:-1]
        c2 = closed[-2]
        result = detect_crt_bias({"1day": candles})
        assert result is not None
        assert result.sweep_level == c2.low

    def test_anchor_datetime_is_c3(self) -> None:
        candles = self._candles()
        closed = candles[:-1]
        c3 = closed[-1]
        result = detect_crt_bias({"1day": candles})
        assert result is not None
        assert result.anchor_datetime == c3.datetime


# ---------------------------------------------------------------------------
# SC-DET-CRT-2: 3-candle bearish pattern
# ---------------------------------------------------------------------------


class TestSCDETCRT23CandleBearish:
    def _candles(self) -> list:
        # c1: reference; c2: sweeps above c1.high; c3: closes below c2.open and c1.high
        # Avoid 2-candle bearish on (c2,c3): need c3.high NOT > c2.high, OR c3 not bearish, OR c3.close >= c2.high
        # Ensure c3.high <= c2.high so 2-candle condition fails
        c1 = make_candle(datetime="2024-01-13 00:00:00", open=1.10150, high=1.10200, low=1.09900, close=1.10000)
        c2 = make_candle(datetime="2024-01-14 00:00:00", open=1.10100, high=1.10400, low=1.09950, close=1.10200)
        c3 = make_candle(datetime="2024-01-15 00:00:00", open=1.10300, high=1.10350, low=1.09950, close=1.10050)
        live = make_candle(datetime="2024-01-16 00:00:00")
        return [c1, c2, c3, live]

    def test_bias_is_bearish(self) -> None:
        result = detect_crt_bias({"1day": self._candles()})
        assert result is not None
        assert result.bias is Bias.BEARISH

    def test_pattern_is_3candle(self) -> None:
        result = detect_crt_bias({"1day": self._candles()})
        assert result is not None
        assert result.pattern == "3-candle"

    def test_tp_level_is_min_c1_c2_low(self) -> None:
        candles = self._candles()
        closed = candles[:-1]
        c1, c2 = closed[-3], closed[-2]
        result = detect_crt_bias({"1day": candles})
        assert result is not None
        assert result.tp_level == min(c1.low, c2.low)

    def test_sweep_level_is_c2_high(self) -> None:
        candles = self._candles()
        closed = candles[:-1]
        c2 = closed[-2]
        result = detect_crt_bias({"1day": candles})
        assert result is not None
        assert result.sweep_level == c2.high


# ---------------------------------------------------------------------------
# SC-DET-CRT-3: 2-candle bullish pattern
# ---------------------------------------------------------------------------


class TestSCDETCRT32CandleBullish:
    def _candles(self) -> list:
        # c1: reference; c2: sweeps below c1.low AND closes bullish above c1.low
        c1 = make_candle(datetime="2024-01-14 00:00:00", open=1.10050, high=1.10200, low=1.10000, close=1.10150)
        c2 = make_candle(datetime="2024-01-15 00:00:00", open=1.09950, high=1.10300, low=1.09800, close=1.10100)
        live = make_candle(datetime="2024-01-16 00:00:00")
        return [c1, c2, live]

    def test_bias_is_bullish(self) -> None:
        result = detect_crt_bias({"1day": self._candles()})
        assert result is not None
        assert result.bias is Bias.BULLISH

    def test_pattern_is_2candle(self) -> None:
        result = detect_crt_bias({"1day": self._candles()})
        assert result is not None
        assert result.pattern == "2-candle"

    def test_tp_level_is_c1_high(self) -> None:
        candles = self._candles()
        closed = candles[:-1]
        c1 = closed[-2]
        result = detect_crt_bias({"1day": candles})
        assert result is not None
        assert result.tp_level == c1.high

    def test_sweep_level_is_c2_low(self) -> None:
        candles = self._candles()
        closed = candles[:-1]
        c2 = closed[-1]
        result = detect_crt_bias({"1day": candles})
        assert result is not None
        assert result.sweep_level == c2.low


# ---------------------------------------------------------------------------
# SC-DET-CRT-4: 2-candle bearish pattern
# ---------------------------------------------------------------------------


class TestSCDETCRT42CandleBearish:
    def _candles(self) -> list:
        # c1: reference; c2: sweeps above c1.high AND closes bearish below c1.high
        c1 = make_candle(datetime="2024-01-14 00:00:00", open=1.10150, high=1.10200, low=1.09900, close=1.10000)
        c2 = make_candle(datetime="2024-01-15 00:00:00", open=1.10250, high=1.10400, low=1.09950, close=1.10050)
        live = make_candle(datetime="2024-01-16 00:00:00")
        return [c1, c2, live]

    def test_bias_is_bearish(self) -> None:
        result = detect_crt_bias({"1day": self._candles()})
        assert result is not None
        assert result.bias is Bias.BEARISH

    def test_pattern_is_2candle(self) -> None:
        result = detect_crt_bias({"1day": self._candles()})
        assert result is not None
        assert result.pattern == "2-candle"

    def test_tp_level_is_c1_low(self) -> None:
        candles = self._candles()
        closed = candles[:-1]
        c1 = closed[-2]
        result = detect_crt_bias({"1day": candles})
        assert result is not None
        assert result.tp_level == c1.low

    def test_sweep_level_is_c2_high(self) -> None:
        candles = self._candles()
        closed = candles[:-1]
        c2 = closed[-1]
        result = detect_crt_bias({"1day": candles})
        assert result is not None
        assert result.sweep_level == c2.high


# ---------------------------------------------------------------------------
# SC-DET-CRT-5: No pattern
# ---------------------------------------------------------------------------


class TestSCDETCRT5NoPattern:
    def test_returns_none_when_no_pattern(self) -> None:
        # Candles that don't satisfy any CRT condition
        c1 = make_candle(datetime="2024-01-14 00:00:00", open=1.10050, high=1.10200, low=1.10000, close=1.10150)
        # c2 stays within c1's range — no sweep
        c2 = make_candle(datetime="2024-01-15 00:00:00", open=1.10080, high=1.10180, low=1.10020, close=1.10100)
        live = make_candle(datetime="2024-01-16 00:00:00")
        result = detect_crt_bias({"1day": [c1, c2, live]})
        assert result is None


# ---------------------------------------------------------------------------
# SC-DET-CRT-6: Priority (3day > 2day > 1day)
# ---------------------------------------------------------------------------


class TestSCDETCRT6Priority:
    def test_3day_takes_priority_over_1day(self) -> None:
        # 1day has a valid 2-candle bullish pattern
        c1_1d = make_candle(datetime="2024-01-14 00:00:00", open=1.10050, high=1.10200, low=1.10000, close=1.10150)
        c2_1d = make_candle(datetime="2024-01-15 00:00:00", open=1.09950, high=1.10300, low=1.09800, close=1.10100)
        live_1d = make_candle(datetime="2024-01-16 00:00:00")

        # 3day has a valid 2-candle bearish pattern
        c1_3d = make_candle(datetime="2024-01-01", open=1.10150, high=1.10200, low=1.09900, close=1.10000)
        c2_3d = make_candle(datetime="2024-01-04", open=1.10250, high=1.10400, low=1.09950, close=1.10050)
        live_3d = make_candle(datetime="2024-01-07")

        result = detect_crt_bias({
            "3day": [c1_3d, c2_3d, live_3d],
            "1day": [c1_1d, c2_1d, live_1d],
        })
        assert result is not None
        assert result.timeframe == "3day"


# ---------------------------------------------------------------------------
# SC-DET-CRT-7: Fewer than 2 closed candles → None
# ---------------------------------------------------------------------------


class TestSCDETCRT7FewerThan2Closed:
    def test_returns_none_with_only_live_candle(self) -> None:
        live = make_candle(datetime="2024-01-15 00:00:00")
        result = detect_crt_bias({"1day": [live]})
        assert result is None

    def test_returns_none_with_empty_list(self) -> None:
        result = detect_crt_bias({"1day": []})
        assert result is None


# ---------------------------------------------------------------------------
# SC-DET-CRT-8: Smoke test with fixture data
# ---------------------------------------------------------------------------


class TestSCDETCRT8Smoke:
    def test_smoke_eurusd_1day(self) -> None:
        from tests.detectors.conftest import load_fixture
        candles = load_fixture("EUR/USD", "1day")
        result = detect_crt_bias({"1day": candles})
        assert result is None or isinstance(result, CRTResult)
