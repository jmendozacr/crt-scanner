from __future__ import annotations

from dataclasses import dataclass

from scanner.data.candle import Candle
from scanner.detectors._common import Bias, exclude_live, find_previous_swing


@dataclass(frozen=True)
class TurtleSoupResult:
    """Result of a Turtle Soup sweep detection on the H4 timeframe."""

    bias: Bias
    swept_level: float
    swept_datetime: str
    ts_candle_datetime: str
    window_start: str
    window_end_hint: str  # Populated by Phase 3; empty string here


def detect_turtle_soup(
    h4_candles: list[Candle],
) -> TurtleSoupResult | None:
    """Detect a Turtle Soup liquidity sweep on H4, deriving bias from the candle direction."""
    closed = exclude_live(h4_candles)
    if len(closed) < 3:
        return None

    ts_candle = closed[-1]

    if ts_candle.close < ts_candle.open:
        internal_bias = Bias.BULLISH
    elif ts_candle.close > ts_candle.open:
        internal_bias = Bias.BEARISH
    else:
        return None

    swing = find_previous_swing(closed, side=internal_bias, anchor_index=len(closed) - 1)
    if swing is None:
        return None

    if internal_bias is Bias.BULLISH:
        if ts_candle.low < swing.low:
            return TurtleSoupResult(
                bias=Bias.BULLISH,
                swept_level=swing.low,
                swept_datetime=swing.datetime,
                ts_candle_datetime=ts_candle.datetime,
                window_start=ts_candle.datetime,
                window_end_hint="",
            )
    else:
        if ts_candle.high > swing.high:
            return TurtleSoupResult(
                bias=Bias.BEARISH,
                swept_level=swing.high,
                swept_datetime=swing.datetime,
                ts_candle_datetime=ts_candle.datetime,
                window_start=ts_candle.datetime,
                window_end_hint="",
            )

    return None
