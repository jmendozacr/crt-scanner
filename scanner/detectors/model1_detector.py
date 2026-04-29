from __future__ import annotations

from dataclasses import dataclass

from scanner.data.candle import Candle
from scanner.detectors._common import Bias, exclude_live

MIN_BODY_RATIO: float = 0.5


@dataclass(frozen=True)
class Model1Result:
    bias: Bias
    model1_candle_datetime: str
    entry_candle_datetime: str
    entry_price: float
    tp_level: float


def detect_model1(
    m15_candles: list[Candle],
    bias: Bias,
    tbs_candle_datetime: str,
    window_end: str,
    tp_level: float,
) -> Model1Result | None:
    closed = exclude_live(m15_candles)
    tbs_dt = tbs_candle_datetime[:16]
    we = window_end[:16]
    after_tbs = [c for c in closed if c.datetime[:16] > tbs_dt and c.datetime[:16] < we]
    if not after_tbs:
        return None
    # find first thick counter-directional candle (Model #1)
    m1_idx = None
    m1_candle = None
    for idx, c in enumerate(after_tbs):
        rng = c.high - c.low
        if rng == 0.0:
            continue
        body_ratio = abs(c.close - c.open) / rng
        if body_ratio < MIN_BODY_RATIO:
            continue
        # counter-directional
        if bias is Bias.BULLISH and c.close < c.open:
            m1_idx = idx
            m1_candle = c
            break
        if bias is Bias.BEARISH and c.close > c.open:
            m1_idx = idx
            m1_candle = c
            break
    if m1_candle is None:
        return None
    # find entry confirmation candle after Model #1
    for entry_c in after_tbs[m1_idx + 1:]:
        if bias is Bias.BULLISH and entry_c.close > m1_candle.open:
            return Model1Result(
                bias=bias,
                model1_candle_datetime=m1_candle.datetime,
                entry_candle_datetime=entry_c.datetime,
                entry_price=m1_candle.open,
                tp_level=tp_level,
            )
        if bias is Bias.BEARISH and entry_c.close < m1_candle.open:
            return Model1Result(
                bias=bias,
                model1_candle_datetime=m1_candle.datetime,
                entry_candle_datetime=entry_c.datetime,
                entry_price=m1_candle.open,
                tp_level=tp_level,
            )
    return None
