from __future__ import annotations

from dataclasses import dataclass

from scanner.data.candle import Candle
from scanner.detectors._common import Bias, exclude_live, in_window


@dataclass(frozen=True)
class FVGResult:
    """Result of a Fair Value Gap detection within a session window."""

    bias: Bias
    gap_high: float
    gap_low: float
    midpoint: float
    candle_1_datetime: str


def detect_fvg(
    m15_candles: list[Candle],
    bias: Bias,
    window_start: str,
    window_end: str,
) -> FVGResult | None:
    """Find the first (oldest) qualifying Fair Value Gap inside the given window."""
    closed = exclude_live(m15_candles)
    if len(closed) < 3:
        return None

    for i in range(len(closed) - 2):
        c1 = closed[i]
        c3 = closed[i + 2]  # c2 (closed[i+1]) is intentionally not inspected

        if not in_window(c1.datetime, window_start, window_end):
            continue

        if bias is Bias.BULLISH:
            # Strict gap: c1's high must be strictly below c3's low
            if c1.high < c3.low:
                gap_low = c1.high
                gap_high = c3.low
                return FVGResult(
                    bias=Bias.BULLISH,
                    gap_high=gap_high,
                    gap_low=gap_low,
                    midpoint=(gap_high + gap_low) / 2,
                    candle_1_datetime=c1.datetime,
                )
        else:
            # Strict gap: c1's low must be strictly above c3's high
            if c1.low > c3.high:
                gap_high = c1.low
                gap_low = c3.high
                return FVGResult(
                    bias=Bias.BEARISH,
                    gap_high=gap_high,
                    gap_low=gap_low,
                    midpoint=(gap_high + gap_low) / 2,
                    candle_1_datetime=c1.datetime,
                )

    return None
