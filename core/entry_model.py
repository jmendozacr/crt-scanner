"""
Entry model (Clutifx) — M15 Order Block detection for CRT setups.

Public API:
    find_engulfing_ob(candles_m15, setup)              -> OBLevel | None
    check_ob_invalidation(candles_m15, ob, direction)  -> bool
    check_ob_touch(candles_m15, ob, direction)         -> bool

Logic (Clutifx model):
    1. After a CRT sweep is confirmed on H4, look at the M15 candles
       that compose the sweep candle's timeframe.
    2. Find the last engulfing pair: for bearish, a bullish M15 candle
       followed immediately by a bearish M15 candle that engulfs it
       (high >= bull.high AND low <= bull.low). The bearish candle is the OB.
       For bullish: mirror logic.
    3. Once an OB is found, monitor subsequent M15 candles for:
       - Invalidation: close beyond the OB's far edge.
       - Touch: price enters the OB zone — trigger the alert.
"""
from __future__ import annotations

import logging

import pandas as pd

from core.crt_detector import CRTSetup, OBLevel

logger = logging.getLogger(__name__)


def find_engulfing_ob(
    candles_m15: pd.DataFrame,
    setup: CRTSetup,
) -> OBLevel | None:
    """
    Search within the setup's time window for an M15 engulfing Order Block.

    Window: [sweep_candle["time"], setup.expires_at)

    For bearish setup:
        Scans for the last consecutive pair (bullish M15, bearish M15) where
        the bearish candle engulfs the bullish one:
            bearish.high >= bullish.high  AND  bearish.low <= bullish.low
        The bearish candle becomes the OB.

    For bullish setup: mirror — last (bearish M15, bullish engulfing) pair.

    Returns OBLevel or None if no engulfing pair is found in the window.
    """
    sweep_time = setup.sweep_candle["time"]
    expires_at = setup.expires_at

    window = candles_m15[
        (candles_m15["time"] >= sweep_time) &
        (candles_m15["time"] < expires_at)
    ].reset_index(drop=True)

    if len(window) < 2:
        return None

    ob: OBLevel | None = None

    for i in range(len(window) - 1):
        c1 = window.iloc[i]
        c2 = window.iloc[i + 1]

        c1_open  = float(c1["open"])
        c1_close = float(c1["close"])
        c1_high  = float(c1["high"])
        c1_low   = float(c1["low"])
        c2_open  = float(c2["open"])
        c2_close = float(c2["close"])
        c2_high  = float(c2["high"])
        c2_low   = float(c2["low"])

        engulfs = c2_high >= c1_high and c2_low <= c1_low

        if setup.direction == "bearish":
            # c1 bullish, c2 bearish engulfing → OB zone is c1 (supply candle)
            if c1_close > c1_open and c2_close < c2_open and engulfs:
                ob = OBLevel(high=c1_high, low=c1_low, formed_at=c2["time"])

        else:  # bullish
            # c1 bearish, c2 bullish engulfing → OB zone is c1 (demand candle)
            if c1_close < c1_open and c2_close > c2_open and engulfs:
                ob = OBLevel(high=c1_high, low=c1_low, formed_at=c2["time"])

    logger.debug(
        "find_engulfing_ob: %s %s → %s",
        setup.pair,
        setup.direction,
        f"OB @ {ob.formed_at}" if ob else "None",
    )
    return ob


def check_ob_invalidation(
    candles_m15: pd.DataFrame,
    ob: OBLevel,
    direction: str,
) -> bool:
    """
    Check if the OB has been invalidated by subsequent M15 candles.

    Bearish: invalidated if any candle after ob.formed_at closes ABOVE ob.high.
    Bullish: invalidated if any candle after ob.formed_at closes BELOW ob.low.
    """
    after = candles_m15[candles_m15["time"] > ob.formed_at]

    if direction == "bearish":
        return bool((after["close"] > ob.high).any())
    else:
        return bool((after["close"] < ob.low).any())


def check_ob_touch(
    candles_m15: pd.DataFrame,
    ob: OBLevel,
    direction: str,
) -> bool:
    """
    Check if price has entered the OB zone after the OB was formed.

    Bearish: any candle after ob.formed_at has high >= ob.low  (enters from above).
    Bullish: any candle after ob.formed_at has low  <= ob.high (enters from below).
    """
    after = candles_m15[candles_m15["time"] > ob.formed_at]

    if direction == "bearish":
        return bool((after["high"] >= ob.low).any())
    else:
        return bool((after["low"] <= ob.high).any())
