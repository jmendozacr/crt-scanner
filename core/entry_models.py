"""
Entry Models — M15 trigger detection inside the H4 CRT zone.

Given a ConfluenceResult (H4 CRT + Daily key level), scans M15 candles for
one of 5 entry setups whose zone overlaps the CRT H4 range.

Entry models:
    OB           — M15 Order Block (reuses detect_obs)
    FVG          — M15 Fair Value Gap (reuses detect_fvgs)
    Breaker Block— former M15 OB that was swept, now acts as opposite S/R
    TWS          — Turtle Soup Wick: wick sweeps recent M15 swing, body returns
    TBS          — Turtle Soup Body: body sweeps recent M15 swing, next candle reverses

Public API:
    find_entry(confluence, m15_df) -> EntrySignal | None
"""
from __future__ import annotations

import logging

import pandas as pd

from core.fvg_detector import detect_fvgs
from core.ob_detector import detect_obs, detect_swings
from core.models import (
    ConfluenceResult,
    Direction,
    ENTRY_PRIORITY,
    EntryModel,
    EntrySignal,
    KeyLevel,
)

logger = logging.getLogger(__name__)

# How many recent M15 candles to look back for Turtle Soup swing searches
_TS_LOOKBACK = 20

_M15 = "M15"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def find_entry(
    confluence: ConfluenceResult,
    m15_df: pd.DataFrame,
) -> EntrySignal | None:
    """
    Find the most recent M15 entry trigger inside the H4 CRT zone.

    Args:
        confluence: ConfluenceResult from htf_confluence (Score A or B).
        m15_df:     M15 DataFrame for the same pair, oldest → newest.

    Returns:
        The highest-priority / most-recent EntrySignal within the CRT zone,
        or None if no valid setup exists.
    """
    signal = confluence.signal
    pair   = signal.pair
    crt_lo = signal.crt_low
    crt_hi = signal.crt_high
    direction = signal.direction

    complete = m15_df[m15_df["complete"]].reset_index(drop=True)
    if len(complete) < 3:
        return None

    candidates: list[EntrySignal] = []
    candidates.extend(_detect_ob_entry(complete, confluence, pair, crt_lo, crt_hi, direction))
    candidates.extend(_detect_fvg_entry(complete, confluence, pair, crt_lo, crt_hi, direction))
    candidates.extend(_detect_breaker_entry(complete, confluence, pair, crt_lo, crt_hi, direction))
    candidates.extend(_detect_tws(complete, confluence, pair, crt_lo, crt_hi, direction))
    candidates.extend(_detect_tbs(complete, confluence, pair, crt_lo, crt_hi, direction))

    if not candidates:
        return None

    best = _best(candidates)
    logger.debug(
        "find_entry: %d candidates → best=%s for %s", len(candidates), best.entry_model.value, pair
    )
    return best


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _in_zone(entry_lo: float, entry_hi: float, crt_lo: float, crt_hi: float) -> bool:
    """True when the entry zone overlaps the CRT range."""
    return entry_lo <= crt_hi and entry_hi >= crt_lo


def _make(
    confluence: ConfluenceResult,
    model: EntryModel,
    zone_lo: float,
    zone_hi: float,
    time,
    pair: str,
) -> EntrySignal:
    return EntrySignal(
        confluence=confluence,
        entry_model=model,
        entry_zone_low=min(zone_lo, zone_hi),
        entry_zone_high=max(zone_lo, zone_hi),
        time=time,
        pair=pair,
    )


def _best(candidates: list[EntrySignal]) -> EntrySignal:
    """
    Return the most recent signal; break ties by highest ENTRY_PRIORITY.
    """
    return max(
        candidates,
        key=lambda s: (s.time, ENTRY_PRIORITY[s.entry_model]),
    )


# ---------------------------------------------------------------------------
# 1. Order Block M15
# ---------------------------------------------------------------------------

def _detect_ob_entry(
    complete: pd.DataFrame,
    confluence: ConfluenceResult,
    pair: str,
    crt_lo: float,
    crt_hi: float,
    direction: Direction,
) -> list[EntrySignal]:
    obs: list[KeyLevel] = detect_obs(complete, pair, _M15)
    result = []
    for ob in obs:
        if ob.direction != direction:
            continue
        if _in_zone(ob.low, ob.high, crt_lo, crt_hi):
            result.append(_make(confluence, EntryModel.ORDER_BLOCK, ob.low, ob.high, ob.time, pair))
    return result


# ---------------------------------------------------------------------------
# 2. FVG M15
# ---------------------------------------------------------------------------

def _detect_fvg_entry(
    complete: pd.DataFrame,
    confluence: ConfluenceResult,
    pair: str,
    crt_lo: float,
    crt_hi: float,
    direction: Direction,
) -> list[EntrySignal]:
    fvgs: list[KeyLevel] = detect_fvgs(complete, pair, _M15)
    result = []
    for fvg in fvgs:
        if fvg.direction != direction:
            continue
        if _in_zone(fvg.low, fvg.high, crt_lo, crt_hi):
            result.append(_make(confluence, EntryModel.FVG, fvg.low, fvg.high, fvg.time, pair))
    return result


# ---------------------------------------------------------------------------
# 3. Breaker Block
# ---------------------------------------------------------------------------

def _detect_breaker_entry(
    complete: pd.DataFrame,
    confluence: ConfluenceResult,
    pair: str,
    crt_lo: float,
    crt_hi: float,
    direction: Direction,
) -> list[EntrySignal]:
    """
    A Breaker Block is a former OB that was invalidated (price closed through
    the zone) and now acts as support/resistance in the opposite direction.

    Bullish OB broken (close < ob.low) → BEARISH Breaker
    Bearish OB broken (close > ob.high) → BULLISH Breaker
    """
    obs: list[KeyLevel] = detect_obs(complete, pair, _M15)
    result = []
    n = len(complete)

    for ob in obs:
        # Find the row index of this OB's candle
        ob_idx_series = complete.index[complete["time"] == ob.time]
        if ob_idx_series.empty:
            continue
        ob_idx = int(ob_idx_series[0])

        # Scan candles after the OB was formed
        broken = False
        last_break_time = None
        for j in range(ob_idx + 1, n):
            c = complete.iloc[j]
            if ob.direction == Direction.BULLISH and float(c["close"]) < ob.low:
                broken = True
                last_break_time = c["time"]
            elif ob.direction == Direction.BEARISH and float(c["close"]) > ob.high:
                broken = True
                last_break_time = c["time"]

        if not broken:
            continue

        # The breaker acts in the opposite direction
        breaker_dir = (
            Direction.BEARISH if ob.direction == Direction.BULLISH else Direction.BULLISH
        )
        if breaker_dir != direction:
            continue
        if _in_zone(ob.low, ob.high, crt_lo, crt_hi):
            result.append(
                _make(confluence, EntryModel.BREAKER_BLOCK, ob.low, ob.high, last_break_time, pair)
            )

    return result


# ---------------------------------------------------------------------------
# 4. Turtle Soup Wick (TWS)
# ---------------------------------------------------------------------------

def _detect_tws(
    complete: pd.DataFrame,
    confluence: ConfluenceResult,
    pair: str,
    crt_lo: float,
    crt_hi: float,
    direction: Direction,
) -> list[EntrySignal]:
    """
    Wick sweep of a recent M15 swing.

    BULLISH: candle.low < swing.low AND candle.close > swing.low
    BEARISH: candle.high > swing.high AND candle.close < swing.high
    """
    swings: list[KeyLevel] = detect_swings(complete, pair, _M15)
    n = len(complete)
    result = []

    for swing in swings:
        swing_idx_series = complete.index[complete["time"] == swing.time]
        if swing_idx_series.empty:
            continue
        swing_idx = int(swing_idx_series[0])

        # Only look at candles in the last _TS_LOOKBACK rows after the swing
        start = max(swing_idx + 1, n - _TS_LOOKBACK)
        for j in range(start, n):
            c = complete.iloc[j]

            if direction == Direction.BULLISH and swing.type.value == "Swing Low":
                if float(c["low"]) < swing.low and float(c["close"]) > swing.low:
                    zone_lo, zone_hi = swing.low, float(c["close"])
                    if _in_zone(zone_lo, zone_hi, crt_lo, crt_hi):
                        result.append(
                            _make(confluence, EntryModel.TURTLE_SOUP_WICK, zone_lo, zone_hi, c["time"], pair)
                        )

            elif direction == Direction.BEARISH and swing.type.value == "Swing High":
                if float(c["high"]) > swing.high and float(c["close"]) < swing.high:
                    zone_lo, zone_hi = float(c["close"]), swing.high
                    if _in_zone(zone_lo, zone_hi, crt_lo, crt_hi):
                        result.append(
                            _make(confluence, EntryModel.TURTLE_SOUP_WICK, zone_lo, zone_hi, c["time"], pair)
                        )
    return result


# ---------------------------------------------------------------------------
# 5. Turtle Soup Body (TBS)
# ---------------------------------------------------------------------------

def _detect_tbs(
    complete: pd.DataFrame,
    confluence: ConfluenceResult,
    pair: str,
    crt_lo: float,
    crt_hi: float,
    direction: Direction,
) -> list[EntrySignal]:
    """
    Body sweep of a recent M15 swing followed by reversal on next candle.

    BULLISH: candle.close < swing.low  AND  next.close > swing.low
    BEARISH: candle.close > swing.high AND  next.close < swing.high
    """
    swings: list[KeyLevel] = detect_swings(complete, pair, _M15)
    n = len(complete)
    result = []

    for swing in swings:
        swing_idx_series = complete.index[complete["time"] == swing.time]
        if swing_idx_series.empty:
            continue
        swing_idx = int(swing_idx_series[0])

        start = max(swing_idx + 1, n - _TS_LOOKBACK)
        for j in range(start, n - 1):   # need j+1 for reversal candle
            c    = complete.iloc[j]
            nxt  = complete.iloc[j + 1]

            if direction == Direction.BULLISH and swing.type.value == "Swing Low":
                if (float(c["close"]) < swing.low
                        and float(nxt["close"]) > swing.low):
                    zone_lo, zone_hi = float(c["close"]), swing.low
                    if _in_zone(zone_lo, zone_hi, crt_lo, crt_hi):
                        result.append(
                            _make(confluence, EntryModel.TURTLE_SOUP_BODY, zone_lo, zone_hi, nxt["time"], pair)
                        )

            elif direction == Direction.BEARISH and swing.type.value == "Swing High":
                if (float(c["close"]) > swing.high
                        and float(nxt["close"]) < swing.high):
                    zone_lo, zone_hi = swing.high, float(c["close"])
                    if _in_zone(zone_lo, zone_hi, crt_lo, crt_hi):
                        result.append(
                            _make(confluence, EntryModel.TURTLE_SOUP_BODY, zone_lo, zone_hi, nxt["time"], pair)
                        )
    return result
