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


# ---------------------------------------------------------------------------
# Key Levels (Fase 3)
# ---------------------------------------------------------------------------

class KeyLevelType(str, Enum):
    FVG = "FVG"
    ORDER_BLOCK = "Order Block"
    SWING_HIGH = "Swing High"
    SWING_LOW = "Swing Low"


class Score(str, Enum):
    A = "A"   # 3 TFs alineados (Daily key level + H4 CRT + M15 confirmado)
    B = "B"   # Daily + H4 alineados, M15 aún no confirma (pre-alerta)


@dataclass(frozen=True, slots=True)
class KeyLevel:
    type: KeyLevelType
    direction: Direction  # BULLISH = zona de soporte, BEARISH = zona de resistencia
    high: float           # límite superior de la zona
    low: float            # límite inferior de la zona
    time: datetime        # timestamp de la vela que originó el nivel
    pair: str
    granularity: str      # TF en que fue detectado (normalmente "D")

    def __repr__(self) -> str:
        return (
            f"KeyLevel({self.type.value} {self.direction.value} {self.pair} "
            f"{self.granularity} {self.low:.5f}–{self.high:.5f} @ {self.time.date()})"
        )


@dataclass(frozen=True, slots=True)
class ConfluenceResult:
    signal: CRTSignal
    key_level: KeyLevel | None  # None → Score B
    score: Score
    aligned: bool

    def __repr__(self) -> str:
        kl = repr(self.key_level) if self.key_level else "none"
        return f"Confluence(Score {self.score.value} | {self.signal!r} | {kl})"
