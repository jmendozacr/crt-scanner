from __future__ import annotations

from dataclasses import dataclass

from scanner.data.candle import Candle
from scanner.detectors._common import Bias, exclude_live
from scanner.detectors.crt_bias import CRTResult


@dataclass(frozen=True)
class Swing:
    """A 1-bar fractal swing point on a closed candle series."""

    kind: str    # "SH" | "SL"
    price: float
    index: int
    datetime: str


def _find_swings(closed: list[Candle]) -> list[Swing]:
    swings: list[Swing] = []
    for i in range(1, len(closed) - 1):
        prev, curr, nxt = closed[i - 1], closed[i], closed[i + 1]
        if curr.high > prev.high and curr.high > nxt.high:
            swings.append(Swing("SH", curr.high, i, curr.datetime))
        if curr.low < prev.low and curr.low < nxt.low:
            swings.append(Swing("SL", curr.low, i, curr.datetime))
    return swings


def _detect_bos(
    closed: list[Candle],
    swings: list[Swing],
) -> tuple[Bias, Swing, Candle, int] | None:
    if not swings:
        return None
    for k in range(len(closed) - 1, -1, -1):
        c = closed[k]
        candidates = sorted(
            [s for s in swings if s.index < k],
            key=lambda s: s.index,
            reverse=True,
        )
        broken_sh = next(
            (s for s in candidates if s.kind == "SH" and c.close > s.price),
            None,
        )
        broken_sl = next(
            (s for s in candidates if s.kind == "SL" and c.close < s.price),
            None,
        )
        if broken_sh and broken_sl:
            chosen = broken_sh if broken_sh.index >= broken_sl.index else broken_sl
            bias = Bias.BULLISH if chosen.kind == "SH" else Bias.BEARISH
            return (bias, chosen, c, k)
        if broken_sh:
            return (Bias.BULLISH, broken_sh, c, k)
        if broken_sl:
            return (Bias.BEARISH, broken_sl, c, k)
    return None


def _resolve_tp(
    swings: list[Swing],
    bias: Bias,
    anchor_index: int,
    sweep_level: float,
) -> float:
    target = "SH" if bias is Bias.BULLISH else "SL"
    for s in swings:
        if s.index > anchor_index and s.kind == target:
            return s.price
    return sweep_level


def detect_smc_bias(candles_1d: list[Candle]) -> CRTResult | None:
    closed = exclude_live(candles_1d)
    if len(closed) < 5:
        return None

    swings = _find_swings(closed)
    if not swings:
        return None

    bos = _detect_bos(closed, swings)
    if bos is None:
        return None
    bias, broken_swing, breaking_candle, breaking_index = bos

    prev = _detect_bos(closed[:breaking_index], swings)
    if prev is None:
        pattern = "BOS"
    else:
        pattern = "CHoCH" if prev[0] != bias else "BOS"

    sweep_level = broken_swing.price
    anchor_datetime = breaking_candle.datetime
    tp_level = _resolve_tp(swings, bias, breaking_index, sweep_level)

    return CRTResult(
        bias=bias,
        timeframe="1day",
        pattern=pattern,
        tp_level=tp_level,
        sweep_level=sweep_level,
        anchor_datetime=anchor_datetime,
    )
