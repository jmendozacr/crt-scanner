from __future__ import annotations

from scanner.data.candle import Candle
from scanner.detectors._common import Bias
from scripts.backtest_engine import exclude_live_with_dup, verify_tp


def _c(
    dt: str,
    high: float = 1.1,
    low: float = 0.9,
    close: float = 1.05,
    open_: float = 1.0,
) -> Candle:
    return Candle(datetime=dt, open=open_, high=high, low=low, close=close, volume=100.0)


# ---------------------------------------------------------------------------
# exclude_live_with_dup
# ---------------------------------------------------------------------------


def test_exclude_live_with_dup_empty() -> None:
    assert exclude_live_with_dup([]) == []


def test_exclude_live_with_dup_appends_last() -> None:
    candles = [_c(f"2024-01-0{i} 00:00:00") for i in range(1, 4)]
    result = exclude_live_with_dup(candles)
    assert len(result) == 4
    assert result[-1] == result[-2]
    assert result[-1] == candles[-1]


# ---------------------------------------------------------------------------
# verify_tp
# ---------------------------------------------------------------------------


def test_verify_tp_bullish_win() -> None:
    candles = [_c("2024-01-01 00:00:00", high=2.0)]
    result, bars = verify_tp(Bias.BULLISH.value, 1.5, candles)
    assert result == "WIN"
    assert bars == 1


def test_verify_tp_bullish_no_hit() -> None:
    candles = [_c(f"2024-01-0{i} 00:00:00", high=1.0) for i in range(1, 4)]
    result, bars = verify_tp(Bias.BULLISH.value, 2.0, candles)
    assert result == "LOSS"
    assert bars == -1


def test_verify_tp_bearish_win() -> None:
    candles = [_c("2024-01-01 00:00:00", low=0.5)]
    result, bars = verify_tp(Bias.BEARISH.value, 0.8, candles)
    assert result == "WIN"
    assert bars == 1


def test_verify_tp_exactly_at_tp() -> None:
    """Boundary: high == tp_level should be a WIN (inclusive)."""
    candles = [_c("2024-01-01 00:00:00", high=1.5)]
    result, bars = verify_tp(Bias.BULLISH.value, 1.5, candles)
    assert result == "WIN"
    assert bars == 1
