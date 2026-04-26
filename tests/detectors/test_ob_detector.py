"""Tests for scanner.detectors.ob_detector — SC-DET-OB-1 through SC-DET-OB-7."""
from __future__ import annotations

from scanner.detectors._common import Bias
from scanner.detectors.ob_detector import OrderBlockResult, detect_order_block

from tests.detectors.conftest import load_fixture, make_candle, make_doji

WIN_START = "2024-01-15 08:00"
WIN_END = "2024-01-15 12:00"
WIDE_START = "2000-01-01 00:00"
WIDE_END = "2099-12-31 23:59"


# ---------------------------------------------------------------------------
# SC-DET-OB-1: Bullish Order Block detected
# ---------------------------------------------------------------------------


class TestSCDETOB1BullishOB:
    def _candles(self) -> list:
        ob = make_candle("2024-01-15 09:00:00", open=1.10100, high=1.10200, low=1.09900, close=1.10000)
        conf = make_candle("2024-01-15 09:15:00", open=1.09980, high=1.10300, low=1.09850, close=1.10250)
        live = make_candle("2024-01-15 09:30:00")
        return [ob, conf, live]

    def test_returns_result(self) -> None:
        result = detect_order_block(self._candles(), Bias.BULLISH, WIN_START, WIN_END)
        assert result is not None

    def test_bias_is_bullish(self) -> None:
        result = detect_order_block(self._candles(), Bias.BULLISH, WIN_START, WIN_END)
        assert result is not None
        assert result.bias is Bias.BULLISH

    def test_ob_high_and_low(self) -> None:
        candles = self._candles()
        ob = candles[0]
        result = detect_order_block(candles, Bias.BULLISH, WIN_START, WIN_END)
        assert result is not None
        assert result.ob_high == ob.high
        assert result.ob_low == ob.low

    def test_ob_datetime(self) -> None:
        candles = self._candles()
        ob = candles[0]
        result = detect_order_block(candles, Bias.BULLISH, WIN_START, WIN_END)
        assert result is not None
        assert result.ob_datetime == ob.datetime

    def test_confirmation_datetime(self) -> None:
        candles = self._candles()
        conf = candles[1]
        result = detect_order_block(candles, Bias.BULLISH, WIN_START, WIN_END)
        assert result is not None
        assert result.confirmation_datetime == conf.datetime


# ---------------------------------------------------------------------------
# SC-DET-OB-2: Bearish Order Block detected
# ---------------------------------------------------------------------------


class TestSCDETOB2BearishOB:
    def _candles(self) -> list:
        ob = make_candle("2024-01-15 09:00:00", open=1.09900, high=1.10100, low=1.09800, close=1.10050)
        conf = make_candle("2024-01-15 09:15:00", open=1.10050, high=1.10200, low=1.09700, close=1.09800)
        live = make_candle("2024-01-15 09:30:00")
        return [ob, conf, live]

    def test_bias_is_bearish(self) -> None:
        result = detect_order_block(self._candles(), Bias.BEARISH, WIN_START, WIN_END)
        assert result is not None
        assert result.bias is Bias.BEARISH

    def test_ob_high_and_low(self) -> None:
        candles = self._candles()
        ob = candles[0]
        result = detect_order_block(candles, Bias.BEARISH, WIN_START, WIN_END)
        assert result is not None
        assert result.ob_high == ob.high
        assert result.ob_low == ob.low


# ---------------------------------------------------------------------------
# SC-DET-OB-3: OB candle outside window → None
# ---------------------------------------------------------------------------


class TestSCDETOB3OutsideWindow:
    def test_returns_none_when_ob_before_window(self) -> None:
        ob = make_candle("2024-01-15 07:59:59", open=1.10100, high=1.10200, low=1.09900, close=1.10000)
        conf = make_candle("2024-01-15 08:00:59", open=1.09980, high=1.10300, low=1.09850, close=1.10250)
        live = make_candle("2024-01-15 08:15:00")
        result = detect_order_block([ob, conf, live], Bias.BULLISH, WIN_START, WIN_END)
        assert result is None

    def test_returns_none_when_ob_after_window(self) -> None:
        ob = make_candle("2024-01-15 12:00:00", open=1.10100, high=1.10200, low=1.09900, close=1.10000)
        conf = make_candle("2024-01-15 12:15:00", open=1.09980, high=1.10300, low=1.09850, close=1.10250)
        live = make_candle("2024-01-15 12:30:00")
        result = detect_order_block([ob, conf, live], Bias.BULLISH, WIN_START, WIN_END)
        assert result is None


# ---------------------------------------------------------------------------
# SC-DET-OB-4: Multiple valid OBs → last (most recent) is returned
# ---------------------------------------------------------------------------


class TestSCDETOB4MultipleOBsLastReturned:
    def test_returns_last_ob(self) -> None:
        ob_a = make_candle("2024-01-15 08:00:00", open=1.10100, high=1.10200, low=1.09900, close=1.10000)
        conf_a = make_candle("2024-01-15 08:15:00", open=1.09980, high=1.10300, low=1.09850, close=1.10250)
        ob_b = make_candle("2024-01-15 09:00:00", open=1.10200, high=1.10350, low=1.10050, close=1.10100)
        conf_b = make_candle("2024-01-15 09:15:00", open=1.10080, high=1.10450, low=1.10000, close=1.10380)
        live = make_candle("2024-01-15 09:30:00")
        result = detect_order_block([ob_a, conf_a, ob_b, conf_b, live], Bias.BULLISH, WIN_START, WIN_END)
        assert result is not None
        assert result.ob_datetime == ob_b.datetime


# ---------------------------------------------------------------------------
# SC-DET-OB-5: Doji candle is rejected as OB
# ---------------------------------------------------------------------------


class TestSCDETOB5DojiRejected:
    def test_returns_none_when_only_ob_is_doji(self) -> None:
        doji_ob = make_doji("2024-01-15 09:00:00", open=1.10050, high=1.10200, low=1.09900)
        conf = make_candle("2024-01-15 09:15:00", open=1.09980, high=1.10300, low=1.09850, close=1.10250)
        live = make_candle("2024-01-15 09:30:00")
        result = detect_order_block([doji_ob, conf, live], Bias.BULLISH, WIN_START, WIN_END)
        assert result is None


# ---------------------------------------------------------------------------
# SC-DET-OB-6: 0 or 1 closed candles → None
# ---------------------------------------------------------------------------


class TestSCDETOB60ClosedCandles:
    def test_returns_none_with_only_live_candle(self) -> None:
        live = make_candle("2024-01-15 09:00:00")
        result = detect_order_block([live], Bias.BULLISH, WIN_START, WIN_END)
        assert result is None

    def test_returns_none_with_empty_list(self) -> None:
        result = detect_order_block([], Bias.BULLISH, WIN_START, WIN_END)
        assert result is None


# ---------------------------------------------------------------------------
# SC-DET-OB-7: Smoke test with real EUR/USD M15 fixture
# ---------------------------------------------------------------------------


class TestSCDETOB7Smoke:
    def test_smoke_eurusd_15min_bullish(self) -> None:
        candles = load_fixture("EUR/USD", "15min")
        result = detect_order_block(candles, Bias.BULLISH, WIDE_START, WIDE_END)
        assert result is None or isinstance(result, OrderBlockResult)
        if result is not None:
            assert result.ob_high > result.ob_low

    def test_smoke_eurusd_15min_bearish(self) -> None:
        candles = load_fixture("EUR/USD", "15min")
        result = detect_order_block(candles, Bias.BEARISH, WIDE_START, WIDE_END)
        assert result is None or isinstance(result, OrderBlockResult)
        if result is not None:
            assert result.ob_high > result.ob_low
