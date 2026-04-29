from __future__ import annotations

from dataclasses import dataclass

from scanner.data.candle import Candle
from scanner.detectors._common import Bias, exclude_live, find_previous_swing


@dataclass(frozen=True)
class TBSResult:
    bias: Bias
    swept_body_level: float
    swept_swing_datetime: str
    tbs_candle_datetime: str
    window_start: str
    window_end_hint: str


def detect_tbs(
    m15_candles: list[Candle],
    htf_bias: Bias,
    window_start: str,
    window_end: str,
) -> TBSResult | None:
    ws = window_start[:16]
    we = window_end[:16]
    all_closed = exclude_live(m15_candles)
    in_window = [c for c in all_closed if ws <= c.datetime[:16] < we]
    if len(in_window) < 3:
        return None
    # scan latest→earliest within window
    for i in range(len(in_window) - 1, 0, -1):
        cand = in_window[i]
        # anchor_index in the FULL closed list
        try:
            full_idx = all_closed.index(cand)
        except ValueError:
            continue
        swing = find_previous_swing(all_closed, side=htf_bias, anchor_index=full_idx)
        if swing is None:
            continue
        if htf_bias is Bias.BULLISH:
            body_low = min(swing.open, swing.close)
            if cand.low < body_low and cand.close > body_low:
                return TBSResult(
                    bias=Bias.BULLISH,
                    swept_body_level=body_low,
                    swept_swing_datetime=swing.datetime,
                    tbs_candle_datetime=cand.datetime,
                    window_start=window_start,
                    window_end_hint="",
                )
        else:
            body_high = max(swing.open, swing.close)
            if cand.high > body_high and cand.close < body_high:
                return TBSResult(
                    bias=Bias.BEARISH,
                    swept_body_level=body_high,
                    swept_swing_datetime=swing.datetime,
                    tbs_candle_datetime=cand.datetime,
                    window_start=window_start,
                    window_end_hint="",
                )
    return None
