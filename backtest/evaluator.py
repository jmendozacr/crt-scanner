"""
Single-trade outcome evaluation for the CRT backtest.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from core.models import Direction, EntrySignal


def _pip_multiplier(pair: str) -> float:
    """Return 100.0 for JPY pairs, 10000.0 for all others."""
    return 100.0 if "JPY" in pair else 10_000.0


@dataclass
class TradeResult:
    entry: EntrySignal
    entry_price: float          # midpoint of entry_zone_low/high
    sl_price: float             # crt_low (bull) or crt_high (bear)
    tp_price: float             # entry ± risk × rr
    outcome: str                # "WIN" | "LOSS" | "OPEN"
    pnl_pips: float | None      # positive = win, negative = loss, None = OPEN
    close_time: datetime | None # candle time that triggered resolution


def evaluate_trade(
    entry: EntrySignal,
    future_candles: pd.DataFrame,
    rr: float,
) -> TradeResult:
    """
    Evaluate a single trade by scanning candles after the entry trigger.

    - SL = crt_low (BULLISH) or crt_high (BEARISH)
    - TP = entry_price + risk * rr (BULLISH) or entry_price - risk * rr (BEARISH)
    - Scans future_candles in order; first to touch TP or SL wins.
    - Returns OPEN if neither level is reached within the available data.
    """
    if rr <= 0:
        raise ValueError(f"rr must be positive, got {rr}")

    signal = entry.confluence.signal
    direction = signal.direction
    entry_price = (entry.entry_zone_low + entry.entry_zone_high) / 2

    if direction == Direction.BULLISH:
        sl_price = signal.crt_low
        risk = entry_price - sl_price
        tp_price = entry_price + risk * rr
    else:
        sl_price = signal.crt_high
        risk = sl_price - entry_price
        tp_price = entry_price - risk * rr

    # Degenerate case: no meaningful risk
    if risk <= 0:
        return TradeResult(
            entry=entry, entry_price=entry_price,
            sl_price=sl_price, tp_price=tp_price,
            outcome="OPEN", pnl_pips=None, close_time=None,
        )

    mult = _pip_multiplier(entry.pair)

    for row in future_candles.itertuples(index=False):
        if direction == Direction.BULLISH:
            if row.high >= tp_price:
                return TradeResult(
                    entry=entry, entry_price=entry_price,
                    sl_price=sl_price, tp_price=tp_price,
                    outcome="WIN",
                    pnl_pips=round(risk * rr * mult, 1),
                    close_time=row.time,
                )
            if row.low <= sl_price:
                return TradeResult(
                    entry=entry, entry_price=entry_price,
                    sl_price=sl_price, tp_price=tp_price,
                    outcome="LOSS",
                    pnl_pips=round(-risk * mult, 1),
                    close_time=row.time,
                )
        else:  # BEARISH
            if row.low <= tp_price:
                return TradeResult(
                    entry=entry, entry_price=entry_price,
                    sl_price=sl_price, tp_price=tp_price,
                    outcome="WIN",
                    pnl_pips=round(risk * rr * mult, 1),
                    close_time=row.time,
                )
            if row.high >= sl_price:
                return TradeResult(
                    entry=entry, entry_price=entry_price,
                    sl_price=sl_price, tp_price=tp_price,
                    outcome="LOSS",
                    pnl_pips=round(-risk * mult, 1),
                    close_time=row.time,
                )

    # Neither TP nor SL was reached
    return TradeResult(
        entry=entry, entry_price=entry_price,
        sl_price=sl_price, tp_price=tp_price,
        outcome="OPEN", pnl_pips=None, close_time=None,
    )
