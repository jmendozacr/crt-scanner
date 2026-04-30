from __future__ import annotations

import dataclasses
import json
from datetime import datetime, timezone
from pathlib import Path

from scanner.data.candle import Candle
from scanner.data.fetcher import TwelveDataFetcher


def _cache_path(symbol: str, timeframe: str, cache_dir: Path) -> Path:
    safe = symbol.replace("/", "_")
    return cache_dir / f"{safe}_{timeframe}.json"


def fetch_and_cache(
    symbol: str,
    timeframe: str,
    outputsize: int,
    fetcher: TwelveDataFetcher,
    cache_dir: Path = Path("cache/backtest"),
    no_fetch: bool = False,
) -> list[dict]:
    path = _cache_path(symbol, timeframe, cache_dir)
    if path.exists():
        meta = json.loads(path.read_text(encoding="utf-8"))
        if meta.get("outputsize", 0) >= outputsize:
            return meta["candles"]
    if no_fetch:
        raise FileNotFoundError(
            f"Cache missing or stale for {symbol} {timeframe}. Run without --no-fetch first."
        )
    candles = fetcher.fetch(symbol, timeframe, outputsize=outputsize)
    raw = [dataclasses.asdict(c) for c in candles]
    cache_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "outputsize": outputsize,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "candles": raw,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return raw


def load_candles(
    symbol: str,
    timeframe: str,
    cache_dir: Path = Path("cache/backtest"),
) -> list[Candle]:
    path = _cache_path(symbol, timeframe, cache_dir)
    if not path.exists():
        raise FileNotFoundError(f"No cache found for {symbol} {timeframe} at {path}")
    meta = json.loads(path.read_text(encoding="utf-8"))
    return [Candle(**d) for d in meta["candles"]]
