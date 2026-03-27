"""
HTF Confluence — crosses H4 CRT signals with Daily key levels.

Logic:
    BULLISH CRT (swept low, expects move up to CRT HIGH):
        → look for BULLISH key levels (FVG / OB / Swing Low) on the Daily
          where the CRT LOW falls inside the key level zone.

    BEARISH CRT (swept high, expects move down to CRT LOW):
        → look for BEARISH key levels (FVG / OB / Swing High) on the Daily
          where the CRT HIGH falls inside the key level zone.

Score:
    A — CRT signal aligns with a Daily key level
    B — CRT signal found, no Daily key level aligned (pre-alert)

Public API:
    get_key_levels(store, pair)                   -> list[KeyLevel]
    check_confluence(signal, key_levels, tol)     -> ConfluenceResult
    run_confluence(signals, store, pair)           -> list[ConfluenceResult]
"""
from __future__ import annotations

import logging

from data.candle_store import CandleStore
from core.fvg_detector import detect_fvgs
from core.ob_detector import detect_obs, detect_swings
from core.models import (
    ConfluenceResult,
    CRTSignal,
    Direction,
    KeyLevel,
    KeyLevelType,
    Score,
)

logger = logging.getLogger(__name__)

# Tolerance expressed as a fraction of the CRT range size.
# E.g. 0.1 = allow the price to be up to 10 % of (crt_high - crt_low) outside
# the key level zone and still count as confluence.
_DEFAULT_TOLERANCE_RATIO = 0.1

# Daily granularity used for key level lookups
_HTF_GRAN = "D"


def get_key_levels(store: CandleStore, pair: str) -> list[KeyLevel]:
    """
    Collect all Daily key levels for `pair` from the candle store.

    Runs FVG, OB and Swing detectors on the Daily DataFrame and returns
    all results merged into a single list sorted oldest → newest.

    Args:
        store: populated CandleStore instance.
        pair:  internal pair name, e.g. "EUR_USD".

    Returns:
        List of KeyLevel from the Daily TF, sorted by time ascending.
    """
    df = store.get(pair, _HTF_GRAN)
    if df.empty:
        logger.warning("get_key_levels: no Daily data for %s", pair)
        return []

    levels: list[KeyLevel] = []
    levels.extend(detect_fvgs(df, pair, _HTF_GRAN))
    levels.extend(detect_obs(df, pair, _HTF_GRAN))
    levels.extend(detect_swings(df, pair, _HTF_GRAN))

    levels.sort(key=lambda kl: kl.time)
    logger.debug(
        "get_key_levels: %d levels for %s (FVG=%d OB=%d Swing=%d)",
        len(levels),
        pair,
        sum(1 for kl in levels if kl.type == KeyLevelType.FVG),
        sum(1 for kl in levels if kl.type == KeyLevelType.ORDER_BLOCK),
        sum(1 for kl in levels if kl.type in (KeyLevelType.SWING_HIGH, KeyLevelType.SWING_LOW)),
    )
    return levels


def check_confluence(
    signal: CRTSignal,
    key_levels: list[KeyLevel],
    tolerance_ratio: float = _DEFAULT_TOLERANCE_RATIO,
) -> ConfluenceResult:
    """
    Check whether `signal` aligns with any key level.

    The price point checked against key levels:
        BULLISH CRT → crt_low  (where price swept before the expected move up)
        BEARISH CRT → crt_high (where price swept before the expected move down)

    A key level matches when:
        key_level.low - tol <= price <= key_level.high + tol

    where tol = tolerance_ratio * (signal.crt_high - signal.crt_low).

    Among all matching levels, the most recent one is returned (most relevant).

    Args:
        signal:           H4 CRTSignal to check.
        key_levels:       Daily key levels for the same pair.
        tolerance_ratio:  Fractional tolerance on the CRT range size.

    Returns:
        ConfluenceResult with Score.A if aligned, Score.B otherwise.
    """
    if signal.direction == Direction.BULLISH:
        price = signal.crt_low
        wanted_direction = Direction.BULLISH
    else:
        price = signal.crt_high
        wanted_direction = Direction.BEARISH

    crt_range = signal.crt_high - signal.crt_low
    tol = tolerance_ratio * crt_range

    # Filter to same direction, then check price within zone
    candidates = [
        kl for kl in key_levels
        if kl.direction == wanted_direction
        and (kl.low - tol) <= price <= (kl.high + tol)
    ]

    if not candidates:
        return ConfluenceResult(
            signal=signal,
            key_level=None,
            score=Score.B,
            aligned=False,
        )

    # Most recent key level is most relevant
    best = max(candidates, key=lambda kl: kl.time)
    return ConfluenceResult(
        signal=signal,
        key_level=best,
        score=Score.A,
        aligned=True,
    )


def run_confluence(
    signals: list[CRTSignal],
    store: CandleStore,
    pair: str,
    tolerance_ratio: float = _DEFAULT_TOLERANCE_RATIO,
) -> list[ConfluenceResult]:
    """
    Run confluence check for all `signals` of the given `pair`.

    Convenience wrapper that fetches key levels once and checks each signal.

    Args:
        signals:          List of H4 CRTSignal objects for `pair`.
        store:            CandleStore with Daily data loaded.
        pair:             e.g. "EUR_USD".
        tolerance_ratio:  Passed through to check_confluence.

    Returns:
        List of ConfluenceResult, same order as `signals`.
    """
    if not signals:
        return []

    key_levels = get_key_levels(store, pair)
    return [check_confluence(s, key_levels, tolerance_ratio) for s in signals]
