from __future__ import annotations

import json
import pathlib

import pytest

from scanner.data.candle import Candle

_FIXTURES_DIR = pathlib.Path(__file__).parent.parent / "fixtures"


def load_fixture(symbol: str, timeframe: str) -> list[Candle]:
    filename = f"{symbol.replace('/', '_')}_{timeframe}.json"
    path = _FIXTURES_DIR / filename
    if not path.exists():
        pytest.skip(f"Fixture file missing: {path}")
    data = json.loads(path.read_text())
    return [Candle.from_api(row) for row in data]


def make_candle(
    datetime: str = "2024-01-15 08:00:00",
    open: float = 1.10000,
    high: float = 1.10100,
    low: float = 1.09900,
    close: float = 1.10050,
    volume: float = 1000.0,
) -> Candle:
    return Candle(
        datetime=datetime,
        open=open,
        high=high,
        low=low,
        close=close,
        volume=volume,
    )


def make_bullish(
    datetime: str = "2024-01-15 08:00:00",
    open: float = 1.10000,
    high: float = 1.10100,
    low: float = 1.09900,
    close: float = 1.10080,
    volume: float = 1000.0,
) -> Candle:
    return Candle(
        datetime=datetime,
        open=open,
        high=high,
        low=low,
        close=close,
        volume=volume,
    )


def make_bearish(
    datetime: str = "2024-01-15 08:00:00",
    open: float = 1.10100,
    high: float = 1.10200,
    low: float = 1.09900,
    close: float = 1.09950,
    volume: float = 1000.0,
) -> Candle:
    return Candle(
        datetime=datetime,
        open=open,
        high=high,
        low=low,
        close=close,
        volume=volume,
    )


def make_doji(
    datetime: str = "2024-01-15 08:00:00",
    open: float = 1.10000,
    high: float = 1.10100,
    low: float = 1.09900,
    volume: float = 1000.0,
) -> Candle:
    return Candle(
        datetime=datetime,
        open=open,
        high=high,
        low=low,
        close=open,
        volume=volume,
    )
