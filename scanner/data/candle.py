from dataclasses import dataclass


@dataclass(frozen=True)
class Candle:
    datetime: str
    open: float
    high: float
    low: float
    close: float
    volume: float

    @classmethod
    def from_api(cls, raw: dict) -> "Candle":
        return cls(
            datetime=raw["datetime"],
            open=float(raw["open"]),
            high=float(raw["high"]),
            low=float(raw["low"]),
            close=float(raw["close"]),
            volume=float(raw.get("volume", "0") or "0"),
        )
