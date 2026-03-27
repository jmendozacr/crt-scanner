"""
Low-level sweep-detection helpers.

All functions take pandas Series rows (columns: open, high, low, close, ...).
Pure functions — no state, no side effects.
"""
from __future__ import annotations

import pandas as pd


def swept_high(candle: pd.Series, reference: pd.Series) -> bool:
    """Candle's wick went above the reference candle's high."""
    return float(candle["high"]) > float(reference["high"])


def swept_low(candle: pd.Series, reference: pd.Series) -> bool:
    """Candle's wick went below the reference candle's low."""
    return float(candle["low"]) < float(reference["low"])


def closed_below_high(candle: pd.Series, reference: pd.Series) -> bool:
    """Candle closed back below the reference candle's high (swept & returned)."""
    return float(candle["close"]) < float(reference["high"])


def closed_above_low(candle: pd.Series, reference: pd.Series) -> bool:
    """Candle closed back above the reference candle's low (swept & returned)."""
    return float(candle["close"]) > float(reference["low"])


def is_inside_bar(candle: pd.Series, outer: pd.Series) -> bool:
    """Candle's full range (high AND low) is inside the outer candle's range."""
    return (
        float(candle["high"]) < float(outer["high"])
        and float(candle["low"]) > float(outer["low"])
    )
