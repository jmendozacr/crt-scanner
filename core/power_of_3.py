"""
Power of 3 — classifies each candle's role in the CRT cycle.

Accumulation  → candle stays within the prior range (building energy)
Manipulation  → candle sweeps the prior high OR low (the liquidity grab)
Distribution  → candle closes back inside after a sweep (the actual move)
Unknown       → first candle of the series, or ambiguous
"""
from __future__ import annotations

from enum import Enum

import pandas as pd

from core.liquidity_sweeper import (
    closed_above_low,
    closed_below_high,
    swept_high,
    swept_low,
)


class Phase(str, Enum):
    ACCUMULATION = "ACCUMULATION"
    MANIPULATION = "MANIPULATION"
    DISTRIBUTION = "DISTRIBUTION"
    UNKNOWN = "UNKNOWN"


def classify_candles(df: pd.DataFrame) -> list[Phase]:
    """
    Classify each candle in `df` as ACCUMULATION, MANIPULATION, DISTRIBUTION,
    or UNKNOWN relative to the immediately prior candle.

    Args:
        df: DataFrame with columns [time, open, high, low, close, ...],
            ordered oldest → newest. Only complete candles should be passed.

    Returns:
        List of Phase values, one per row. First row is always UNKNOWN.
    """
    if df.empty:
        return []

    phases: list[Phase] = [Phase.UNKNOWN]  # first candle has no prior reference

    for i in range(1, len(df)):
        candle = df.iloc[i]
        prior = df.iloc[i - 1]

        sweeps_h = swept_high(candle, prior)
        sweeps_l = swept_low(candle, prior)

        if sweeps_h and closed_below_high(candle, prior):
            # Swept the high AND closed back — bearish distribution
            phases.append(Phase.DISTRIBUTION)
        elif sweeps_l and closed_above_low(candle, prior):
            # Swept the low AND closed back — bullish distribution
            phases.append(Phase.DISTRIBUTION)
        elif sweeps_h or sweeps_l:
            # Swept but did NOT close back — still in manipulation
            phases.append(Phase.MANIPULATION)
        else:
            phases.append(Phase.ACCUMULATION)

    return phases
