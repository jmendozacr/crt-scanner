"""
Single-trade outcome evaluation for the CRT backtest (Clutifx model).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from core.crt_detector import CRTSetup, OBLevel


def _pip_multiplier(pair: str) -> float:
    """Return 100.0 for JPY pairs, 10000.0 for all others."""
    return 100.0 if "JPY" in pair else 10_000.0


@dataclass
class TradeResult:
    pair:         str
    direction:    str            # "bullish" | "bearish"
    entry_price:  float          # midpoint of OB zone
    sl_price:     float          # crt_l (bull) or crt_h (bear)
    tp_price:     float          # entry ± risk × rr
    outcome:      str            # "WIN" | "LOSS" | "OPEN"
    pnl_pips:     float | None   # positive = win, negative = loss, None = OPEN
    close_time:   datetime | None


def evaluate_setup_trade(
    setup: CRTSetup,
    ob: OBLevel,
    future_candles: pd.DataFrame,
    rr: float,
) -> TradeResult:
    """
    Evaluate a Clutifx trade outcome.

    Entry:  midpoint of ob.low / ob.high
    SL:     crt_l (bullish) or crt_h (bearish)
    TP:     entry ± risk × rr
    Scans future_candles in order; first candle to touch TP or SL decides outcome.
    Returns OPEN if neither level is reached within the available data.
    """
    if rr <= 0:
        raise ValueError(f"rr must be positive, got {rr}")

    entry_price = (ob.high + ob.low) / 2

    if setup.direction == "bullish":
        sl_price = setup.crt_l
        risk     = entry_price - sl_price
        tp_price = entry_price + risk * rr
    else:
        sl_price = setup.crt_h
        risk     = sl_price - entry_price
        tp_price = entry_price - risk * rr

    if risk <= 0:
        return TradeResult(
            pair=setup.pair, direction=setup.direction,
            entry_price=entry_price, sl_price=sl_price, tp_price=tp_price,
            outcome="OPEN", pnl_pips=None, close_time=None,
        )

    mult = _pip_multiplier(setup.pair)

    for row in future_candles.itertuples(index=False):
        if setup.direction == "bullish":
            if row.high >= tp_price:
                return TradeResult(
                    pair=setup.pair, direction=setup.direction,
                    entry_price=entry_price, sl_price=sl_price, tp_price=tp_price,
                    outcome="WIN",
                    pnl_pips=round(risk * rr * mult, 1),
                    close_time=row.time,
                )
            if row.low <= sl_price:
                return TradeResult(
                    pair=setup.pair, direction=setup.direction,
                    entry_price=entry_price, sl_price=sl_price, tp_price=tp_price,
                    outcome="LOSS",
                    pnl_pips=round(-risk * mult, 1),
                    close_time=row.time,
                )
        else:  # bearish
            if row.low <= tp_price:
                return TradeResult(
                    pair=setup.pair, direction=setup.direction,
                    entry_price=entry_price, sl_price=sl_price, tp_price=tp_price,
                    outcome="WIN",
                    pnl_pips=round(risk * rr * mult, 1),
                    close_time=row.time,
                )
            if row.high >= sl_price:
                return TradeResult(
                    pair=setup.pair, direction=setup.direction,
                    entry_price=entry_price, sl_price=sl_price, tp_price=tp_price,
                    outcome="LOSS",
                    pnl_pips=round(-risk * mult, 1),
                    close_time=row.time,
                )

    return TradeResult(
        pair=setup.pair, direction=setup.direction,
        entry_price=entry_price, sl_price=sl_price, tp_price=tp_price,
        outcome="OPEN", pnl_pips=None, close_time=None,
    )
