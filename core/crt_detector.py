"""
CRT Detector — detects all 4 CRT models on a DataFrame of candles.

Public API:
    detect(df, pair, granularity) -> list[CRTSignal]

Input df columns: [time, open, high, low, close, volume, complete]
    - Ordered oldest → newest (output of CandleStore.get())
    - The function internally filters to complete == True rows only.

The 4 models detected:
    TWO_CANDLE   — sweep + close in a single candle
    THREE_CANDLE — ref + manipulation + distribution (3 separate candles)
    MULTI_CANDLE — ref + 2-5 sweep candles + final close-back
    INSIDE_BAR   — ref is an inside bar; sweep targets inside bar's range
"""
from __future__ import annotations

import logging

import pandas as pd

from core.liquidity_sweeper import (
    closed_above_low,
    closed_below_high,
    is_inside_bar,
    swept_high,
    swept_low,
)
from core.models import MODEL_PRIORITY, CRTModel, CRTSignal, Direction

logger = logging.getLogger(__name__)

# Maximum number of sweep candles to consider for Multi Candle CRT
_MULTI_MAX_SWEEPS = 5


def detect(
    df: pd.DataFrame,
    pair: str,
    granularity: str,
) -> list[CRTSignal]:
    """
    Detect all valid CRT patterns in `df`.

    Args:
        df:          DataFrame with OHLCV columns, oldest → newest.
        pair:        Internal pair name, e.g. "EUR_USD".
        granularity: Granularity string, e.g. "H4".

    Returns:
        List of CRTSignal, deduplicated by (sweep_time, direction).
        Empty list if no patterns found or insufficient data.
    """
    complete = df[df["complete"]].reset_index(drop=True)
    n = len(complete)

    if n < 2:
        logger.debug("detect: not enough complete candles (%d) for %s %s", n, pair, granularity)
        return []

    raw: list[CRTSignal] = []

    for i in range(1, n):
        raw.extend(_two_candle(complete, i, pair, granularity))

        if i >= 2:
            raw.extend(_three_candle(complete, i, pair, granularity))
            raw.extend(_inside_bar(complete, i, pair, granularity))

        if i >= 3:
            raw.extend(_multi_candle(complete, i, pair, granularity))

    signals = _deduplicate(raw)
    logger.debug(
        "detect: %d raw → %d unique signals for %s %s", len(raw), len(signals), pair, granularity
    )
    return signals


# ---------------------------------------------------------------------------
# Model detectors (private)
# ---------------------------------------------------------------------------

def _two_candle(
    df: pd.DataFrame, i: int, pair: str, granularity: str
) -> list[CRTSignal]:
    ref = df.iloc[i - 1]
    sweep = df.iloc[i]
    signals = []

    if swept_low(sweep, ref) and closed_above_low(sweep, ref):
        signals.append(_signal(CRTModel.TWO_CANDLE, Direction.BULLISH, ref, sweep, pair, granularity))

    if swept_high(sweep, ref) and closed_below_high(sweep, ref):
        signals.append(_signal(CRTModel.TWO_CANDLE, Direction.BEARISH, ref, sweep, pair, granularity))

    return signals


def _three_candle(
    df: pd.DataFrame, i: int, pair: str, granularity: str
) -> list[CRTSignal]:
    ref = df.iloc[i - 2]
    manip = df.iloc[i - 1]
    dist = df.iloc[i]
    signals = []

    # Bullish: manip sweeps ref's low; dist closes back above ref's low
    if swept_low(manip, ref) and float(dist["close"]) > float(ref["low"]):
        signals.append(_signal(CRTModel.THREE_CANDLE, Direction.BULLISH, ref, dist, pair, granularity))

    # Bearish: manip sweeps ref's high; dist closes back below ref's high
    if swept_high(manip, ref) and float(dist["close"]) < float(ref["high"]):
        signals.append(_signal(CRTModel.THREE_CANDLE, Direction.BEARISH, ref, dist, pair, granularity))

    return signals


def _inside_bar(
    df: pd.DataFrame, i: int, pair: str, granularity: str
) -> list[CRTSignal]:
    outer = df.iloc[i - 2]
    inside = df.iloc[i - 1]
    sweep = df.iloc[i]
    signals = []

    if not is_inside_bar(inside, outer):
        return signals

    # CRT range is the inside bar's high/low — not the outer candle's
    if swept_low(sweep, inside) and closed_above_low(sweep, inside):
        signals.append(_signal(CRTModel.INSIDE_BAR, Direction.BULLISH, inside, sweep, pair, granularity))

    if swept_high(sweep, inside) and closed_below_high(sweep, inside):
        signals.append(_signal(CRTModel.INSIDE_BAR, Direction.BEARISH, inside, sweep, pair, granularity))

    return signals


def _multi_candle(
    df: pd.DataFrame, i: int, pair: str, granularity: str
) -> list[CRTSignal]:
    """
    Multi Candle CRT: ref + N sweep candles (2 ≤ N ≤ _MULTI_MAX_SWEEPS) + final close-back.

    The sweep candles all breach the same side of the ref without closing back.
    The final candle closes back inside.
    """
    signals = []
    final = df.iloc[i]

    # n = total sweep candles between ref and final (at least 2)
    for n in range(2, min(_MULTI_MAX_SWEEPS + 1, i)):
        ref_idx = i - n - 1
        if ref_idx < 0:
            break
        ref = df.iloc[ref_idx]
        sweeps = [df.iloc[ref_idx + k] for k in range(1, n + 1)]

        # Bullish: all sweeps go below ref.low; final closes back above ref.low
        if (
            all(swept_low(s, ref) for s in sweeps)
            and float(final["close"]) > float(ref["low"])
        ):
            signals.append(_signal(CRTModel.MULTI_CANDLE, Direction.BULLISH, ref, final, pair, granularity))

        # Bearish: all sweeps go above ref.high; final closes back below ref.high
        if (
            all(swept_high(s, ref) for s in sweeps)
            and float(final["close"]) < float(ref["high"])
        ):
            signals.append(_signal(CRTModel.MULTI_CANDLE, Direction.BEARISH, ref, final, pair, granularity))

    return signals


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _signal(
    model: CRTModel,
    direction: Direction,
    ref: pd.Series,
    trigger: pd.Series,
    pair: str,
    granularity: str,
) -> CRTSignal:
    return CRTSignal(
        model=model,
        direction=direction,
        crt_high=float(ref["high"]),
        crt_low=float(ref["low"]),
        ref_time=ref["time"],
        sweep_time=trigger["time"],
        pair=pair,
        granularity=granularity,
    )


def _deduplicate(signals: list[CRTSignal]) -> list[CRTSignal]:
    """
    For each (sweep_time, direction) key, keep only the highest-priority model.
    Priority: INSIDE_BAR > THREE_CANDLE > MULTI_CANDLE > TWO_CANDLE
    """
    best: dict[tuple, CRTSignal] = {}
    for sig in signals:
        key = (sig.sweep_time, sig.direction)
        existing = best.get(key)
        if existing is None or MODEL_PRIORITY[sig.model] > MODEL_PRIORITY[existing.model]:
            best[key] = sig
    # Return sorted by sweep_time for deterministic output
    return sorted(best.values(), key=lambda s: s.sweep_time)
