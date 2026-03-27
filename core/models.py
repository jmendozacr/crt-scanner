"""
Shared dataclasses and enums used across all core modules.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class Direction(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"


class CRTModel(str, Enum):
    TWO_CANDLE = "2 Candle CRT"
    THREE_CANDLE = "3 Candle CRT"
    MULTI_CANDLE = "Multi Candle CRT"
    INSIDE_BAR = "Inside Bar CRT"


# Detection priority for deduplication (higher = more specific, wins ties)
MODEL_PRIORITY: dict[CRTModel, int] = {
    CRTModel.TWO_CANDLE: 1,
    CRTModel.MULTI_CANDLE: 2,
    CRTModel.THREE_CANDLE: 3,
    CRTModel.INSIDE_BAR: 4,
}


@dataclass(frozen=True, slots=True)
class CRTSignal:
    model: CRTModel
    direction: Direction
    crt_high: float    # high of the reference candle (the CRT range)
    crt_low: float     # low of the reference candle (the CRT range)
    ref_time: datetime   # timestamp of the reference (accumulation) candle
    sweep_time: datetime # timestamp of the candle that confirmed the sweep
    pair: str
    granularity: str

    def __repr__(self) -> str:
        arrow = "▲" if self.direction == Direction.BULLISH else "▼"
        return (
            f"CRTSignal({self.model.value} {arrow} {self.pair} {self.granularity} "
            f"H={self.crt_high} L={self.crt_low} @ {self.sweep_time.isoformat()})"
        )
