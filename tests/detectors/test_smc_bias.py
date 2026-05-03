from __future__ import annotations

import pytest

from scanner.detectors._common import Bias
from scanner.detectors.crt_bias import CRTResult
from scanner.detectors.smc_bias import (
    Swing,
    _detect_bos,
    _find_swings,
    _resolve_tp,
    detect_smc_bias,
)

from tests.detectors.conftest import load_fixture, make_candle


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _c(dt: str, high: float, low: float, close: float, open: float = 0.0) -> object:
    return make_candle(datetime=dt, open=open or low, high=high, low=low, close=close)


# ---------------------------------------------------------------------------
# TestFindSwings
# ---------------------------------------------------------------------------


class TestFindSwings:
    def test_swing_high_detected(self) -> None:
        closed = [
            _c("2024-01-01", high=1.10, low=1.09, close=1.095),
            _c("2024-01-02", high=1.12, low=1.10, close=1.11),  # SH
            _c("2024-01-03", high=1.11, low=1.09, close=1.095),
        ]
        swings = _find_swings(closed)
        sh = [s for s in swings if s.kind == "SH"]
        assert len(sh) == 1
        assert sh[0].price == 1.12
        assert sh[0].index == 1

    def test_swing_low_detected(self) -> None:
        closed = [
            _c("2024-01-01", high=1.12, low=1.10, close=1.11),
            _c("2024-01-02", high=1.11, low=1.08, close=1.09),  # SL
            _c("2024-01-03", high=1.12, low=1.10, close=1.11),
        ]
        swings = _find_swings(closed)
        sl = [s for s in swings if s.kind == "SL"]
        assert len(sl) == 1
        assert sl[0].price == 1.08
        assert sl[0].index == 1

    def test_outside_bar_registers_both(self) -> None:
        closed = [
            _c("2024-01-01", high=1.11, low=1.10, close=1.105),
            _c("2024-01-02", high=1.13, low=1.08, close=1.11),  # SH + SL
            _c("2024-01-03", high=1.12, low=1.09, close=1.10),
        ]
        swings = _find_swings(closed)
        kinds = [s.kind for s in swings if s.index == 1]
        assert "SH" in kinds
        assert "SL" in kinds

    def test_outside_bar_sh_before_sl(self) -> None:
        closed = [
            _c("2024-01-01", high=1.11, low=1.10, close=1.105),
            _c("2024-01-02", high=1.13, low=1.08, close=1.11),
            _c("2024-01-03", high=1.12, low=1.09, close=1.10),
        ]
        swings = _find_swings(closed)
        at_1 = [s for s in swings if s.index == 1]
        assert at_1[0].kind == "SH"
        assert at_1[1].kind == "SL"

    def test_endpoints_not_fractals(self) -> None:
        closed = [
            _c("2024-01-01", high=1.15, low=1.08, close=1.12),  # first — no neighbors on left
            _c("2024-01-02", high=1.11, low=1.10, close=1.105),
            _c("2024-01-03", high=1.16, low=1.07, close=1.12),  # last — no neighbors on right
        ]
        swings = _find_swings(closed)
        indices = {s.index for s in swings}
        assert 0 not in indices
        assert 2 not in indices

    def test_empty_on_fewer_than_three_candles(self) -> None:
        assert _find_swings([]) == []
        assert _find_swings([_c("2024-01-01", 1.10, 1.09, 1.095)]) == []
        assert _find_swings([
            _c("2024-01-01", 1.10, 1.09, 1.095),
            _c("2024-01-02", 1.11, 1.10, 1.105),
        ]) == []


# ---------------------------------------------------------------------------
# TestDetectBOS
# ---------------------------------------------------------------------------


class TestDetectBOS:
    def _series_with_sh(self) -> tuple[list, list[Swing]]:
        closed = [
            _c("2024-01-01", high=1.10, low=1.09, close=1.095),
            _c("2024-01-02", high=1.12, low=1.10, close=1.11),   # SH at i=1
            _c("2024-01-03", high=1.11, low=1.09, close=1.095),
            _c("2024-01-04", high=1.13, low=1.10, close=1.125),  # breaks SH → BOS bullish
        ]
        swings = _find_swings(closed)
        return closed, swings

    def test_bullish_bos_detected(self) -> None:
        closed, swings = self._series_with_sh()
        result = _detect_bos(closed, swings)
        assert result is not None
        bias, _, _, _ = result
        assert bias is Bias.BULLISH

    def test_bearish_bos_detected(self) -> None:
        closed = [
            _c("2024-01-01", high=1.12, low=1.10, close=1.11),
            _c("2024-01-02", high=1.11, low=1.08, close=1.09),   # SL at i=1
            _c("2024-01-03", high=1.12, low=1.10, close=1.11),
            _c("2024-01-04", high=1.10, low=1.085, close=1.07),  # breaks SL → BOS bearish
        ]
        swings = _find_swings(closed)
        result = _detect_bos(closed, swings)
        assert result is not None
        bias, _, _, _ = result
        assert bias is Bias.BEARISH

    def test_tie_break_uses_highest_swing_index(self) -> None:
        # close=1.115 breaks SH@index=3(price=1.10) and SL@index=1(price=1.13)
        # SH has higher index (3 > 1) → BULLISH wins
        closed = [make_candle(datetime=f"2024-01-0{i+1}", high=1.15, low=1.10, close=1.12) for i in range(4)]
        closed.append(make_candle(datetime="2024-01-05", high=1.15, low=1.10, close=1.115))
        swings = [
            Swing("SL", 1.13, 1, "2024-01-02"),  # SL at index=1, price=1.13
            Swing("SH", 1.10, 3, "2024-01-04"),  # SH at index=3, price=1.10
        ]
        result = _detect_bos(closed, swings)
        assert result is not None
        bias, broken_swing, _, _ = result
        assert bias is Bias.BULLISH
        assert broken_swing.index == 3

    def test_returns_none_when_no_break(self) -> None:
        closed = [
            _c("2024-01-01", high=1.10, low=1.09, close=1.095),
            _c("2024-01-02", high=1.12, low=1.10, close=1.11),
            _c("2024-01-03", high=1.115, low=1.105, close=1.11),  # never breaks SH
        ]
        swings = _find_swings(closed)
        assert _detect_bos(closed, swings) is None

    def test_returns_none_with_empty_swings(self) -> None:
        closed = [
            _c("2024-01-01", high=1.10, low=1.09, close=1.095),
            _c("2024-01-02", high=1.11, low=1.10, close=1.105),
            _c("2024-01-03", high=1.12, low=1.11, close=1.115),
        ]
        assert _detect_bos(closed, []) is None


# ---------------------------------------------------------------------------
# TestResolveTp
# ---------------------------------------------------------------------------


class TestResolveTp:
    def _swings(self) -> list[Swing]:
        return [
            Swing("SL", 1.08, 1, "2024-01-02"),
            Swing("SH", 1.12, 2, "2024-01-03"),
            Swing("SL", 1.09, 4, "2024-01-05"),
            Swing("SH", 1.14, 6, "2024-01-07"),
        ]

    def test_bullish_returns_first_sh_after_anchor(self) -> None:
        swings = self._swings()
        tp = _resolve_tp(swings, Bias.BULLISH, anchor_index=3, sweep_level=1.09)
        assert tp == 1.14  # SH at index=6

    def test_bearish_returns_first_sl_after_anchor(self) -> None:
        swings = self._swings()
        tp = _resolve_tp(swings, Bias.BEARISH, anchor_index=3, sweep_level=1.12)
        assert tp == 1.09  # SL at index=4

    def test_fallback_to_sweep_level_when_no_opposite_swing(self) -> None:
        swings = [Swing("SH", 1.12, 2, "2024-01-03")]
        tp = _resolve_tp(swings, Bias.BULLISH, anchor_index=5, sweep_level=1.12)
        assert tp == 1.12


# ---------------------------------------------------------------------------
# TestDetectSMCBias
# ---------------------------------------------------------------------------


class TestDetectSMCBias:
    def _bullish_bos_candles(self) -> list:
        # Structure: SL at i=1, SH at i=3, then BOS bullish at i=5
        candles = [
            _c("2024-01-01", high=1.10, low=1.09, close=1.095),
            _c("2024-01-02", high=1.10, low=1.07, close=1.08),   # SL
            _c("2024-01-03", high=1.11, low=1.09, close=1.10),
            _c("2024-01-04", high=1.13, low=1.10, close=1.12),   # SH
            _c("2024-01-05", high=1.12, low=1.10, close=1.11),
            _c("2024-01-06", high=1.14, low=1.11, close=1.135),  # breaks SH → BOS bullish
            _c("2024-01-07", high=1.14, low=1.13, close=1.135),  # live
        ]
        return candles

    def _bearish_bos_candles(self) -> list:
        candles = [
            _c("2024-01-01", high=1.13, low=1.10, close=1.12),
            _c("2024-01-02", high=1.14, low=1.11, close=1.13),   # SH
            _c("2024-01-03", high=1.13, low=1.10, close=1.11),
            _c("2024-01-04", high=1.11, low=1.08, close=1.09),   # SL
            _c("2024-01-05", high=1.12, low=1.10, close=1.11),
            _c("2024-01-06", high=1.10, low=1.075, close=1.078), # breaks SL → BOS bearish
            _c("2024-01-07", high=1.09, low=1.08, close=1.085),  # live
        ]
        return candles

    def test_bullish_bos_returns_correct_result(self) -> None:
        result = detect_smc_bias(self._bullish_bos_candles())
        assert result is not None
        assert result.bias is Bias.BULLISH
        assert result.timeframe == "1day"
        assert result.pattern == "BOS"
        assert isinstance(result, CRTResult)

    def test_bearish_bos_returns_correct_result(self) -> None:
        result = detect_smc_bias(self._bearish_bos_candles())
        assert result is not None
        assert result.bias is Bias.BEARISH
        assert result.timeframe == "1day"
        assert result.pattern == "BOS"

    def test_choch_bullish_after_bearish_structure(self) -> None:
        # bearish BOS (close breaks SL@1), then bullish BOS (close breaks SH@5) → CHoCH
        candles = [
            _c("2024-01-01", high=1.13, low=1.11, close=1.12),
            _c("2024-01-02", high=1.12, low=1.08, close=1.09),   # SL fractal
            _c("2024-01-03", high=1.13, low=1.10, close=1.12),
            _c("2024-01-04", high=1.12, low=1.07, close=1.075),  # breaks SL@1 → bearish BOS
            _c("2024-01-05", high=1.11, low=1.09, close=1.10),
            _c("2024-01-06", high=1.14, low=1.10, close=1.13),   # SH fractal
            _c("2024-01-07", high=1.13, low=1.11, close=1.12),
            _c("2024-01-08", high=1.16, low=1.12, close=1.155),  # breaks SH@5 → CHoCH bullish
            _c("2024-01-09", high=1.16, low=1.15, close=1.155),  # live
        ]
        result = detect_smc_bias(candles)
        assert result is not None
        assert result.bias is Bias.BULLISH
        assert result.pattern == "CHoCH"

    def test_choch_bearish_after_bullish_structure(self) -> None:
        # bullish BOS (close breaks SH@1), then bearish BOS (close breaks SL@5) → CHoCH
        candles = [
            _c("2024-01-01", high=1.12, low=1.10, close=1.11),
            _c("2024-01-02", high=1.14, low=1.11, close=1.13),   # SH fractal
            _c("2024-01-03", high=1.13, low=1.11, close=1.12),
            _c("2024-01-04", high=1.15, low=1.12, close=1.145),  # breaks SH@1 → bullish BOS
            _c("2024-01-05", high=1.14, low=1.12, close=1.13),
            _c("2024-01-06", high=1.13, low=1.09, close=1.10),   # SL fractal
            _c("2024-01-07", high=1.14, low=1.11, close=1.13),
            _c("2024-01-08", high=1.13, low=1.085, close=1.088), # breaks SL@5 → CHoCH bearish
            _c("2024-01-09", high=1.10, low=1.09, close=1.095),  # live
        ]
        result = detect_smc_bias(candles)
        assert result is not None
        assert result.bias is Bias.BEARISH
        assert result.pattern == "CHoCH"

    def test_returns_none_with_fewer_than_five_closed(self) -> None:
        candles = [
            _c("2024-01-01", high=1.10, low=1.09, close=1.095),
            _c("2024-01-02", high=1.11, low=1.10, close=1.105),
            _c("2024-01-03", high=1.12, low=1.10, close=1.11),
            _c("2024-01-04", high=1.10, low=1.09, close=1.095),
            _c("2024-01-05", high=1.11, low=1.10, close=1.105),  # live
        ]
        assert detect_smc_bias(candles) is None

    def test_returns_none_with_no_structure(self) -> None:
        # Linear trend with no fractals (no swing is higher/lower than both neighbors)
        candles = [
            _c("2024-01-01", high=1.10, low=1.09, close=1.095),
            _c("2024-01-02", high=1.11, low=1.10, close=1.105),
            _c("2024-01-03", high=1.12, low=1.11, close=1.115),
            _c("2024-01-04", high=1.13, low=1.12, close=1.125),
            _c("2024-01-05", high=1.14, low=1.13, close=1.135),
            _c("2024-01-06", high=1.15, low=1.14, close=1.145),  # live
        ]
        assert detect_smc_bias(candles) is None

    def test_sweep_level_is_broken_swing_price(self) -> None:
        result = detect_smc_bias(self._bullish_bos_candles())
        assert result is not None
        assert result.sweep_level == 1.13  # SH broken in bullish series

    def test_anchor_datetime_is_breaking_candle(self) -> None:
        result = detect_smc_bias(self._bullish_bos_candles())
        assert result is not None
        assert result.anchor_datetime == "2024-01-06"

    def test_timeframe_always_1day(self) -> None:
        result = detect_smc_bias(self._bullish_bos_candles())
        assert result is not None
        assert result.timeframe == "1day"

    def test_smoke_eurusd_1day_fixture(self) -> None:
        candles = load_fixture("EUR/USD", "1day")
        result = detect_smc_bias(candles)
        assert result is None or isinstance(result, CRTResult)
