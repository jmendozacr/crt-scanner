"""
Order Block (OB) and Swing High/Low detector.

Order Block
-----------
The last candle of opposite color immediately before an impulsive move.

Bullish OB: last BEARISH candle before N consecutive bullish candles that
            close above the OB's high (impulse away from the zone).
    zone: body of the bearish candle (open → close, i.e. open > close)
          low  = close  (bottom of body)
          high = open   (top of body)

Bearish OB: last BULLISH candle before N consecutive bearish candles that
            close below the OB's low.
    zone: body of the bullish candle (open → close, i.e. close > open)
          low  = open
          high = close

Swing Highs / Lows
------------------
A swing high at candle[i] when candle[i].high is the highest of the
surrounding SWING_LOOKBACK candles on each side.
A swing low is the mirror image.

Public API:
    detect_obs(df, pair, granularity)     -> list[KeyLevel]
    detect_swings(df, pair, granularity)  -> list[KeyLevel]
"""
from __future__ import annotations

import logging

import pandas as pd

from core.models import Direction, KeyLevel, KeyLevelType

logger = logging.getLogger(__name__)

_IMPULSE_CANDLES = 2   # minimum consecutive same-direction candles after OB
_SWING_LOOKBACK = 2    # bars on each side to confirm a swing pivot


def detect_obs(
    df: pd.DataFrame,
    pair: str,
    granularity: str,
) -> list[KeyLevel]:
    """
    Detect Order Blocks in `df`.

    Args:
        df:          DataFrame oldest → newest, complete candles only used.
        pair:        e.g. "EUR_USD".
        granularity: e.g. "D".

    Returns:
        List of KeyLevel (type=ORDER_BLOCK) ordered by time ascending.
    """
    complete = df[df["complete"]].reset_index(drop=True)
    n = len(complete)
    min_rows = 1 + _IMPULSE_CANDLES
    if n < min_rows:
        return []

    obs: list[KeyLevel] = []

    for i in range(n - _IMPULSE_CANDLES):
        candle = complete.iloc[i]
        impulse = [complete.iloc[i + j] for j in range(1, _IMPULSE_CANDLES + 1)]

        is_bearish = float(candle["close"]) < float(candle["open"])
        is_bullish = float(candle["close"]) > float(candle["open"])

        # Bullish OB: bearish candle followed by bullish impulse above OB high
        if is_bearish:
            all_bullish = all(float(c["close"]) > float(c["open"]) for c in impulse)
            breaks_above = float(impulse[-1]["close"]) > float(candle["high"])
            if all_bullish and breaks_above:
                obs.append(KeyLevel(
                    type=KeyLevelType.ORDER_BLOCK,
                    direction=Direction.BULLISH,
                    low=float(candle["close"]),   # bottom of bearish body
                    high=float(candle["open"]),   # top of bearish body
                    time=candle["time"],
                    pair=pair,
                    granularity=granularity,
                ))

        # Bearish OB: bullish candle followed by bearish impulse below OB low
        elif is_bullish:
            all_bearish = all(float(c["close"]) < float(c["open"]) for c in impulse)
            breaks_below = float(impulse[-1]["close"]) < float(candle["low"])
            if all_bearish and breaks_below:
                obs.append(KeyLevel(
                    type=KeyLevelType.ORDER_BLOCK,
                    direction=Direction.BEARISH,
                    low=float(candle["open"]),    # bottom of bullish body
                    high=float(candle["close"]),  # top of bullish body
                    time=candle["time"],
                    pair=pair,
                    granularity=granularity,
                ))

    logger.debug("detect_obs: %d OBs found for %s %s", len(obs), pair, granularity)
    return obs


def detect_swings(
    df: pd.DataFrame,
    pair: str,
    granularity: str,
) -> list[KeyLevel]:
    """
    Detect Swing Highs and Swing Lows in `df`.

    A swing high at index i: candle[i].high is strictly greater than the
    high of each of the _SWING_LOOKBACK candles on both sides.

    A swing low is the mirror: candle[i].low is strictly less than the
    low of each surrounding candle.

    Args:
        df:          DataFrame oldest → newest.
        pair:        e.g. "EUR_USD".
        granularity: e.g. "D".

    Returns:
        List of KeyLevel (type=SWING_HIGH or SWING_LOW) ordered by time.
        The zone for a swing high is a 1-pip band around the high (high == low
        for a point level); consumers can apply tolerance when checking.
    """
    complete = df[df["complete"]].reset_index(drop=True)
    n = len(complete)
    lb = _SWING_LOOKBACK

    if n < 2 * lb + 1:
        return []

    swings: list[KeyLevel] = []

    for i in range(lb, n - lb):
        candle = complete.iloc[i]
        left = [complete.iloc[i - k] for k in range(1, lb + 1)]
        right = [complete.iloc[i + k] for k in range(1, lb + 1)]

        pivot_high = float(candle["high"])
        pivot_low = float(candle["low"])

        # Swing High
        if all(pivot_high > float(c["high"]) for c in left + right):
            swings.append(KeyLevel(
                type=KeyLevelType.SWING_HIGH,
                direction=Direction.BEARISH,  # resistance above price
                low=pivot_high,
                high=pivot_high,
                time=candle["time"],
                pair=pair,
                granularity=granularity,
            ))

        # Swing Low
        if all(pivot_low < float(c["low"]) for c in left + right):
            swings.append(KeyLevel(
                type=KeyLevelType.SWING_LOW,
                direction=Direction.BULLISH,  # support below price
                low=pivot_low,
                high=pivot_low,
                time=candle["time"],
                pair=pair,
                granularity=granularity,
            ))

    logger.debug("detect_swings: %d pivots found for %s %s", len(swings), pair, granularity)
    return swings
