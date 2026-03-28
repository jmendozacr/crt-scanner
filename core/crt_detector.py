"""
CRT Detector — detects H4 candle range sweeps (Clutifx refactor).

Public API:
    detect_crt(df, pair, lookback) -> list[CRTSetup]

Logic:
    Takes the last closed H4 candle (sweep_candle) and checks whether
    its wick swept the High or Low of any reference candle within the
    last `lookback` candles, WITHOUT closing through it (no breakout).

    Bearish CRT: sweep.high > ref.high  AND  sweep.close < ref.high
    Bullish CRT: sweep.low  < ref.low   AND  sweep.close > ref.low

Input df columns: [time, open, high, low, close, volume, complete]
    Ordered oldest → newest (output of CandleStore.get()).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

import pandas as pd

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class OBLevel:
    """M15 Order Block zone used by the Clutifx entry model."""
    high: float
    low: float
    formed_at: pd.Timestamp
    invalidated: bool = False


@dataclass
class CRTSetup:
    """
    A detected CRT sweep on H4.

    Status flow:
        "pending"
        → "watching_m15"   (after HTF confluence confirmed in main.py)
        → "ob_formed"      (after find_engulfing_ob() finds the OB)
        → "triggered"      (after OB touch → send alert)
        → "invalidated"    (after OB invalidation)
        → "expired"        (expires_at passed without resolution)
    """
    pair: str
    direction: str              # "bearish" | "bullish"
    ref_candle: pd.Series       # H4 candle whose extreme was swept
    sweep_candle: pd.Series     # H4 candle that made the sweep
    crt_h: float                # ref_candle["high"]
    crt_l: float                # ref_candle["low"]
    expires_at: pd.Timestamp    # sweep_candle["time"] + 4h
    htf_level: object = field(default=None)   # KeyLevel | None, set by main.py
    ob: OBLevel | None = field(default=None)
    status: str = field(default="pending")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_crt(
    df: pd.DataFrame,
    pair: str,
    lookback: int = 10,
) -> list[CRTSetup]:
    """
    Detect H4 CRT sweeps on the last closed candle.

    Args:
        df:       DataFrame with OHLCV columns, oldest → newest.
        pair:     Internal pair name, e.g. "EUR_USD".
        lookback: How many previous candles to check as potential ref_candle.

    Returns:
        List of CRTSetup sorted by proximity to current price (closest first).
        Empty list if no patterns found or insufficient data.
    """
    if df.empty or "complete" not in df.columns:
        return []

    complete = df[df["complete"]].reset_index(drop=True)
    n = len(complete)

    if n < 2:
        logger.debug("detect_crt: not enough complete candles (%d) for %s", n, pair)
        return []

    sweep = complete.iloc[-1]
    # Window: up to `lookback` candles immediately before the sweep candle
    window_start = max(0, n - lookback - 1)
    window = complete.iloc[window_start: n - 1]

    current_price = (float(sweep["high"]) + float(sweep["low"])) / 2
    expires_at = sweep["time"] + pd.Timedelta(hours=4)

    setups: list[CRTSetup] = []

    for _, ref in window.iterrows():
        ref_high = float(ref["high"])
        ref_low = float(ref["low"])
        sw_high = float(sweep["high"])
        sw_low = float(sweep["low"])
        sw_close = float(sweep["close"])

        # Bearish CRT: wick swept above ref.high, body closed back below it
        if sw_high > ref_high and sw_close < ref_high:
            setups.append(CRTSetup(
                pair=pair,
                direction="bearish",
                ref_candle=ref,
                sweep_candle=sweep,
                crt_h=ref_high,
                crt_l=ref_low,
                expires_at=expires_at,
            ))

        # Bullish CRT: wick swept below ref.low, body closed back above it
        if sw_low < ref_low and sw_close > ref_low:
            setups.append(CRTSetup(
                pair=pair,
                direction="bullish",
                ref_candle=ref,
                sweep_candle=sweep,
                crt_h=ref_high,
                crt_l=ref_low,
                expires_at=expires_at,
            ))

    # Sort by proximity to current price — closest range midpoint first
    setups.sort(key=lambda s: abs(current_price - (s.crt_h + s.crt_l) / 2))

    logger.debug(
        "detect_crt: %d setup(s) for %s (lookback=%d)", len(setups), pair, lookback
    )
    return setups
