"""
Fair Value Gap (FVG) detector.

An FVG is a price imbalance between 3 consecutive candles where the wick
of candle[i-2] and the wick of candle[i] do not overlap, leaving a gap
that acts as a magnet for future price action.

Bullish FVG  (support zone):  candle[i-2].high < candle[i].low
    gap zone: low  = candle[i-2].high
              high = candle[i].low

Bearish FVG  (resistance zone): candle[i-2].low > candle[i].high
    gap zone: low  = candle[i].high
              high = candle[i-2].low

Public API:
    detect_fvgs(df, pair, granularity) -> list[KeyLevel]
"""
from __future__ import annotations

import logging

import pandas as pd

from core.models import Direction, KeyLevel, KeyLevelType

logger = logging.getLogger(__name__)


def detect_fvgs(
    df: pd.DataFrame,
    pair: str,
    granularity: str,
) -> list[KeyLevel]:
    """
    Detect all Fair Value Gaps in `df`.

    Args:
        df:          DataFrame with columns [time, open, high, low, close, complete],
                     oldest → newest.
        pair:        Internal pair name, e.g. "EUR_USD".
        granularity: Granularity string, e.g. "D".

    Returns:
        List of KeyLevel (type=FVG) ordered by time ascending.
        Only complete candles are used.
    """
    complete = df[df["complete"]].reset_index(drop=True)
    n = len(complete)

    if n < 3:
        return []

    fvgs: list[KeyLevel] = []

    for i in range(2, n):
        c0 = complete.iloc[i - 2]  # first candle of the trio
        c1 = complete.iloc[i - 1]  # middle candle (impulse)
        c2 = complete.iloc[i]      # third candle

        # Bullish FVG: gap between c0.high and c2.low
        if float(c0["high"]) < float(c2["low"]):
            fvgs.append(KeyLevel(
                type=KeyLevelType.FVG,
                direction=Direction.BULLISH,
                low=float(c0["high"]),
                high=float(c2["low"]),
                time=c1["time"],
                pair=pair,
                granularity=granularity,
            ))

        # Bearish FVG: gap between c2.high and c0.low
        if float(c0["low"]) > float(c2["high"]):
            fvgs.append(KeyLevel(
                type=KeyLevelType.FVG,
                direction=Direction.BEARISH,
                low=float(c2["high"]),
                high=float(c0["low"]),
                time=c1["time"],
                pair=pair,
                granularity=granularity,
            ))

    logger.debug("detect_fvgs: %d FVGs found for %s %s", len(fvgs), pair, granularity)
    return fvgs
