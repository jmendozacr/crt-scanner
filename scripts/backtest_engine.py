from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta

from scanner.data.candle import Candle
from scanner.detectors import detect_turtle_soup, detect_tbs, detect_model1
from scanner.detectors._common import Bias, exclude_live
from scanner.utils.sessions import get_session

MIN_HISTORY: int = 200
LOOKAHEAD: int = 20


@dataclasses.dataclass
class TradeRecord:
    symbol: str
    session: str
    bias: str  # "bullish" or "bearish"
    entry_price: float
    tp_level: float
    sweep_level: float
    result: str  # "WIN" or "LOSS"
    rr: float
    bars_to_tp: int  # -1 if LOSS
    entry_datetime: str
    model1_datetime: str


@dataclasses.dataclass
class FunnelCounts:
    symbol: str
    total_m15_steps: int = 0
    passed_ts: int = 0
    passed_session: int = 0
    passed_tbs: int = 0
    passed_model1: int = 0


def exclude_live_with_dup(candles: list[Candle]) -> list[Candle]:
    """Duplicate last candle so detectors that call exclude_live() still see it."""
    if not candles:
        return []
    return candles + [candles[-1]]


def verify_tp(
    bias: str, tp_level: float, lookahead_candles: list[Candle]
) -> tuple[str, int]:
    for i, c in enumerate(lookahead_candles, start=1):
        if bias == Bias.BULLISH.value and c.high >= tp_level:
            return ("WIN", i)
        if bias == Bias.BEARISH.value and c.low <= tp_level:
            return ("WIN", i)
    return ("LOSS", -1)


def walk_pair(
    symbol: str,
    daily: list[Candle],
    h4: list[Candle],
    m15: list[Candle],
    min_history: int = MIN_HISTORY,
    lookahead: int = LOOKAHEAD,
) -> tuple[list[TradeRecord], FunnelCounts]:
    funnel = FunnelCounts(symbol=symbol)
    trades: list[TradeRecord] = []
    seen_entries: set[str] = set()  # deduplication by entry_datetime

    k = min_history
    while k < len(m15):
        funnel.total_m15_steps += 1
        current_dt = m15[k].datetime  # "%Y-%m-%d %H:%M:%S"

        raw_h4 = [c for c in h4 if c.datetime <= current_dt]
        raw_m15 = m15[: k + 1]

        if not raw_h4 or len(raw_m15) < 2:
            k += 1
            continue

        h4_slice = exclude_live_with_dup(raw_h4)
        m15_slice = exclude_live_with_dup(raw_m15)

        # Stage 1: H4 Turtle Soup (bias derived from candle direction)
        ts = detect_turtle_soup(h4_slice)
        if ts is None or ts.tp_level is None:
            k += 1
            continue
        funnel.passed_ts += 1

        # Stage 2: Session gate
        session = get_session(ts.ts_candle_datetime)
        if session is None:
            k += 1
            continue
        funnel.passed_session += 1

        # Stage 3: TBS window
        ws_dt = datetime.strptime(ts.window_start, "%Y-%m-%d %H:%M:%S")
        we_dt = ws_dt + timedelta(hours=4)
        ws_str = ws_dt.strftime("%Y-%m-%d %H:%M")
        we_str = we_dt.strftime("%Y-%m-%d %H:%M")
        tbs = detect_tbs(m15_slice, ts.bias, ws_str, we_str)
        if tbs is None:
            k += 1
            continue
        funnel.passed_tbs += 1

        # Stage 4: Model #1
        model1 = detect_model1(
            m15_slice, ts.bias, tbs.tbs_candle_datetime, we_str
        )
        if model1 is None:
            k += 1
            continue
        funnel.passed_model1 += 1

        # Deduplication
        if model1.entry_candle_datetime in seen_entries:
            k += 1
            continue
        seen_entries.add(model1.entry_candle_datetime)

        # Find entry_idx in full m15 list
        entry_idx = next(
            (i for i, c in enumerate(m15) if c.datetime == model1.entry_candle_datetime),
            None,
        )
        if entry_idx is None:
            k += 1
            continue

        # TP verification using opposite swing level from Turtle Soup
        result, bars_to_tp = verify_tp(
            ts.bias.value,
            ts.tp_level,
            m15[entry_idx + 1 : entry_idx + 1 + lookahead],
        )

        risk = abs(ts.swept_level - model1.entry_price)
        rr = (
            round(abs(ts.tp_level - model1.entry_price) / risk, 2) if risk > 0 else 0.0
        )

        trades.append(
            TradeRecord(
                symbol=symbol,
                session=session,
                bias=ts.bias.value,
                entry_price=model1.entry_price,
                tp_level=ts.tp_level,
                sweep_level=ts.swept_level,
                result=result,
                rr=rr,
                bars_to_tp=bars_to_tp,
                entry_datetime=model1.entry_candle_datetime,
                model1_datetime=model1.model1_candle_datetime,
            )
        )

        # Advance past the entry bar
        k = entry_idx + 1

    return (trades, funnel)
