from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scanner.data.candle import Candle


class Bias(str, Enum):
    """Direction bias used across all detectors."""

    BULLISH = "bullish"
    BEARISH = "bearish"


def exclude_live(candles: list[Candle]) -> list[Candle]:
    """Return all candles except the last (live) one."""
    return candles[:-1]


def in_window(dt: str, start: str, end: str) -> bool:
    """Return True if dt falls in the half-open interval [start, end)."""
    return start <= dt < end


def is_doji(candle: Candle) -> bool:
    """Return True if the candle has no body (open == close)."""
    return candle.close == candle.open


def find_previous_swing(
    candles: list[Candle],
    side: Bias,
    anchor_index: int,
) -> Candle | None:
    """Walk backward from anchor_index-1 and return the first 1-bar fractal swing.

    A fractal requires both a previous and next neighbor (strict 1-bar fractal).
    BULLISH: curr.low < prev.low AND curr.low < next.low.
    BEARISH: curr.high > prev.high AND curr.high > next.high.
    Returns None if no fractal is found.
    """
    # Need at least prev, curr, and next for a fractal — start one step inside.
    for i in range(anchor_index - 1, 0, -1):
        prev = candles[i - 1]
        curr = candles[i]
        nxt = candles[i + 1]
        if side is Bias.BULLISH:
            if curr.low < prev.low and curr.low < nxt.low:
                return curr
        else:
            if curr.high > prev.high and curr.high > nxt.high:
                return curr
    return None
