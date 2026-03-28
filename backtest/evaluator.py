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
    entry_price:  float          # midpoint of OB zone (c1)
    sl_price:     float          # ob.low (bull) | ob.high (bear)
    tp_price:     float          # setup.crt_h (bull) | setup.crt_l (bear)
    outcome:      str            # "WIN" | "LOSS" | "OPEN"
    pnl_pips:     float | None   # positive = win, negative = loss, None = OPEN
    close_time:   datetime | None


def evaluate_setup_trade(
    setup: CRTSetup,
    ob: OBLevel,
    future_candles: pd.DataFrame,
    rr: float = 0,  # kept for CLI compatibility; TP is determined by CRT level
) -> TradeResult:
    """
    Evaluate a Clutifx trade outcome.

    Entry:  midpoint of ob.low / ob.high  (OB zone = c1 range)
    SL:     ob.low  (bullish) — below the demand candle
            ob.high (bearish) — above the supply candle
    TP:     setup.crt_h (bullish) — the swept CRT high
            setup.crt_l (bearish) — the swept CRT low

    Scans future_candles in order; first candle to touch TP or SL decides outcome.
    Returns OPEN if neither level is reached within the available data.
    """
    # Entry at the near edge of the OB — where the order limit sits:
    # Bullish: ob.high (top of the demand candle, first price touched on retrace)
    # Bearish: ob.low  (bottom of the supply candle, first price touched on retrace)
    if setup.direction == "bullish":
        entry_price = ob.high
        sl_price    = ob.low
        tp_price    = setup.crt_h
        risk        = entry_price - sl_price
    else:
        entry_price = ob.low
        sl_price    = ob.high
        tp_price    = setup.crt_l
        risk        = sl_price - entry_price

    if risk <= 0:
        return TradeResult(
            pair=setup.pair, direction=setup.direction,
            entry_price=entry_price, sl_price=sl_price, tp_price=tp_price,
            outcome="OPEN", pnl_pips=None, close_time=None,
        )

    mult     = _pip_multiplier(setup.pair)
    win_pips = round(abs(tp_price - entry_price) * mult, 1)
    los_pips = round(-risk * mult, 1)

    for row in future_candles.itertuples(index=False):
        if setup.direction == "bullish":
            if row.high >= tp_price:
                return TradeResult(
                    pair=setup.pair, direction=setup.direction,
                    entry_price=entry_price, sl_price=sl_price, tp_price=tp_price,
                    outcome="WIN", pnl_pips=win_pips, close_time=row.time,
                )
            if row.low <= sl_price:
                return TradeResult(
                    pair=setup.pair, direction=setup.direction,
                    entry_price=entry_price, sl_price=sl_price, tp_price=tp_price,
                    outcome="LOSS", pnl_pips=los_pips, close_time=row.time,
                )
        else:  # bearish
            if row.low <= tp_price:
                return TradeResult(
                    pair=setup.pair, direction=setup.direction,
                    entry_price=entry_price, sl_price=sl_price, tp_price=tp_price,
                    outcome="WIN", pnl_pips=win_pips, close_time=row.time,
                )
            if row.high >= sl_price:
                return TradeResult(
                    pair=setup.pair, direction=setup.direction,
                    entry_price=entry_price, sl_price=sl_price, tp_price=tp_price,
                    outcome="LOSS", pnl_pips=los_pips, close_time=row.time,
                )

    return TradeResult(
        pair=setup.pair, direction=setup.direction,
        entry_price=entry_price, sl_price=sl_price, tp_price=tp_price,
        outcome="OPEN", pnl_pips=None, close_time=None,
    )
