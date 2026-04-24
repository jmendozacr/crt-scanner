from __future__ import annotations

from dataclasses import dataclass

from scanner.data.candle import Candle
from scanner.detectors._common import Bias, exclude_live, is_doji


@dataclass(frozen=True)
class CRTResult:
    """Result of a CRT bias detection on a single timeframe."""

    bias: Bias
    timeframe: str
    pattern: str
    tp_level: float
    sweep_level: float
    anchor_datetime: str


def _check_2candle(
    closed: list[Candle],
    tf: str,
) -> CRTResult | None:
    """Try to find a 2-candle CRT pattern in the last two closed candles."""
    if len(closed) < 2:
        return None
    c1, c2 = closed[-2], closed[-1]
    if is_doji(c2):
        return None
    # Bullish: c2 sweeps below c1.low then closes back above it
    if c2.low < c1.low and c2.close > c2.open and c2.close > c1.low:
        return CRTResult(
            bias=Bias.BULLISH,
            timeframe=tf,
            pattern="2-candle",
            tp_level=c1.high,
            sweep_level=c2.low,
            anchor_datetime=c2.datetime,
        )
    # Bearish: c2 sweeps above c1.high then closes back below it
    if c2.high > c1.high and c2.close < c2.open and c2.close < c1.high:
        return CRTResult(
            bias=Bias.BEARISH,
            timeframe=tf,
            pattern="2-candle",
            tp_level=c1.low,
            sweep_level=c2.high,
            anchor_datetime=c2.datetime,
        )
    return None


def _check_3candle(
    closed: list[Candle],
    tf: str,
) -> CRTResult | None:
    """Try to find a 3-candle CRT pattern in the last three closed candles."""
    if len(closed) < 3:
        return None
    c1, c2, c3 = closed[-3], closed[-2], closed[-1]
    if is_doji(c3):
        return None
    # Bullish: c2 sweeps c1.low; c3 reclaims above c2.open and c1.low
    if c2.low < c1.low and c3.close > c2.open and c3.close > c1.low:
        return CRTResult(
            bias=Bias.BULLISH,
            timeframe=tf,
            pattern="3-candle",
            tp_level=max(c1.high, c2.high),  # c2 wick can exceed c1 in a deep sweep
            sweep_level=c2.low,
            anchor_datetime=c3.datetime,
        )
    # Bearish: c2 sweeps c1.high; c3 reclaims below c2.open and c1.high
    if c2.high > c1.high and c3.close < c2.open and c3.close < c1.high:
        return CRTResult(
            bias=Bias.BEARISH,
            timeframe=tf,
            pattern="3-candle",
            tp_level=min(c1.low, c2.low),  # c2 wick can exceed c1 in a deep sweep
            sweep_level=c2.high,
            anchor_datetime=c3.datetime,
        )
    return None


def detect_crt_bias(
    candles_by_tf: dict[str, list[Candle]],
) -> CRTResult | None:
    """Detect the highest-priority CRT bias across 3-day, 2-day, and 1-day timeframes."""
    for tf in ("3day", "2day", "1day"):
        candles = candles_by_tf.get(tf)
        if not candles:
            continue
        closed = exclude_live(candles)
        result = _check_2candle(closed, tf) or _check_3candle(closed, tf)
        if result is not None:
            return result
    return None
