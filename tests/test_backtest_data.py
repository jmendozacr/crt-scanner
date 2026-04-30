from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from scanner.data.candle import Candle
from scripts.backtest_data import _cache_path, fetch_and_cache, load_candles


def _make_candles(n: int = 3) -> list[Candle]:
    return [
        Candle(
            datetime=f"2024-01-{i + 1:02d} 00:00:00",
            open=1.0,
            high=1.1,
            low=0.9,
            close=1.05,
            volume=100.0,
        )
        for i in range(n)
    ]


def _make_fetcher(candles: list[Candle]) -> MagicMock:
    fetcher = MagicMock()
    fetcher.fetch.return_value = candles
    return fetcher


# ---------------------------------------------------------------------------
# fetch_and_cache
# ---------------------------------------------------------------------------


def test_fetch_and_cache_writes_json(tmp_path: Path) -> None:
    candles = _make_candles(3)
    fetcher = _make_fetcher(candles)

    fetch_and_cache("EUR/USD", "1day", 3, fetcher, cache_dir=tmp_path)

    path = _cache_path("EUR/USD", "1day", tmp_path)
    assert path.exists()
    meta = json.loads(path.read_text(encoding="utf-8"))
    assert meta["symbol"] == "EUR/USD"
    assert meta["timeframe"] == "1day"
    assert meta["outputsize"] == 3
    assert len(meta["candles"]) == 3


def test_fetch_and_cache_cache_hit(tmp_path: Path) -> None:
    candles = _make_candles(3)
    fetcher = _make_fetcher(candles)

    # Prime cache with outputsize=2000
    path = _cache_path("EUR/USD", "1day", tmp_path)
    tmp_path.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "symbol": "EUR/USD",
                "timeframe": "1day",
                "outputsize": 2000,
                "fetched_at": "2024-01-01T00:00:00+00:00",
                "candles": [dataclasses.asdict(c) for c in candles],
            }
        ),
        encoding="utf-8",
    )

    fetch_and_cache("EUR/USD", "1day", 2000, fetcher, cache_dir=tmp_path)

    fetcher.fetch.assert_not_called()


def test_fetch_and_cache_stale_refetches(tmp_path: Path) -> None:
    candles = _make_candles(3)
    fetcher = _make_fetcher(candles)

    # Prime cache with small outputsize
    path = _cache_path("EUR/USD", "1day", tmp_path)
    tmp_path.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "symbol": "EUR/USD",
                "timeframe": "1day",
                "outputsize": 10,
                "fetched_at": "2024-01-01T00:00:00+00:00",
                "candles": [dataclasses.asdict(c) for c in candles],
            }
        ),
        encoding="utf-8",
    )

    fetch_and_cache("EUR/USD", "1day", 100, fetcher, cache_dir=tmp_path)

    fetcher.fetch.assert_called_once()


def test_no_fetch_raises_when_missing(tmp_path: Path) -> None:
    fetcher = _make_fetcher(_make_candles())

    with pytest.raises(FileNotFoundError):
        fetch_and_cache("EUR/USD", "1day", 100, fetcher, cache_dir=tmp_path, no_fetch=True)


def test_load_candles_roundtrip(tmp_path: Path) -> None:
    candles = _make_candles(3)
    fetcher = _make_fetcher(candles)

    fetch_and_cache("EUR/USD", "1day", 3, fetcher, cache_dir=tmp_path)
    loaded = load_candles("EUR/USD", "1day", cache_dir=tmp_path)

    assert len(loaded) == 3
    for orig, got in zip(candles, loaded):
        assert orig.datetime == got.datetime
        assert orig.open == got.open
        assert orig.high == got.high
        assert orig.low == got.low
        assert orig.close == got.close
        assert orig.volume == got.volume


def test_load_candles_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_candles("EUR/USD", "1day", cache_dir=tmp_path)
