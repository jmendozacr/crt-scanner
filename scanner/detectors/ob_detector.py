from __future__ import annotations

from dataclasses import dataclass

from scanner.data.candle import Candle
from scanner.detectors._common import Bias, exclude_live, in_window, is_doji


@dataclass(frozen=True)
class OrderBlockResult:
    """Result of an Order Block detection within a session window."""

    bias: Bias
    ob_high: float
    ob_low: float
    ob_datetime: str
    confirmation_datetime: str


def detect_order_block(
    m15_candles: list[Candle],
    bias: Bias,
    window_start: str,
    window_end: str,
) -> OrderBlockResult | None:
    """Find the last (most recent) qualifying Order Block inside the given window.

    Only the OB candle's datetime is checked against the window; the confirmation
    candle (i+1) may legally fall after window_end.
    """
    closed = exclude_live(m15_candles)
    if len(closed) < 2:
        return None

    last_match: OrderBlockResult | None = None

    for i in range(len(closed) - 1):
        ob = closed[i]
        conf = closed[i + 1]

        if not in_window(ob.datetime, window_start, window_end):
            continue
        if is_doji(ob):
            continue

        if bias is Bias.BULLISH:
            # OB must be bearish body; confirmation must fully engulf OB and close bullish
            if (
                ob.close < ob.open
                and conf.high >= ob.high
                and conf.low <= ob.low
                and conf.close > conf.open
            ):
                last_match = OrderBlockResult(
                    bias=Bias.BULLISH,
                    ob_high=ob.high,
                    ob_low=ob.low,
                    ob_datetime=ob.datetime,
                    confirmation_datetime=conf.datetime,
                )
        else:
            # OB must be bullish body; confirmation must fully engulf OB and close bearish
            if (
                ob.close > ob.open
                and conf.high >= ob.high
                and conf.low <= ob.low
                and conf.close < conf.open
            ):
                last_match = OrderBlockResult(
                    bias=Bias.BEARISH,
                    ob_high=ob.high,
                    ob_low=ob.low,
                    ob_datetime=ob.datetime,
                    confirmation_datetime=conf.datetime,
                )

    return last_match
