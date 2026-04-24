import json
import logging
import time
from pathlib import Path

from scanner.data.candle import Candle
from scanner.config import settings

logger = logging.getLogger(__name__)

TTL_BY_TIMEFRAME: dict[str, int] = {
    "1day": 86400,
    "2day": 172800,
    "3day": 259200,
    "4h": 14400,
    "15min": 900,
}


def _cache_path(cache_dir: Path, symbol: str, timeframe: str) -> Path:
    sanitized = symbol.replace("/", "_")
    return cache_dir / f"{sanitized}_{timeframe}.json"


def _is_fresh(fetched_at: float, timeframe: str, now: float) -> bool:
    ttl = TTL_BY_TIMEFRAME[timeframe]
    return (now - fetched_at) < ttl


class CandleCache:
    def __init__(self, fetcher, cache_dir: Path | None = None) -> None:
        self._fetcher = fetcher
        if cache_dir is None:
            self._cache_dir = Path(settings.CACHE_DIR).resolve()
        else:
            self._cache_dir = Path(cache_dir).resolve()
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def get(self, symbol: str, timeframe: str, outputsize: int | None = None) -> list[Candle]:
        path = _cache_path(self._cache_dir, symbol, timeframe)

        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                fetched_at: float = data["fetched_at"]
                if _is_fresh(fetched_at, timeframe, time.time()):
                    return [Candle(**c) for c in data["candles"]]
            except (json.JSONDecodeError, KeyError, OSError) as e:
                logger.warning("Cache read error for %s %s: %s", symbol, timeframe, e)

        candles = self._fetcher.fetch(symbol, timeframe, outputsize)
        self._write(path, symbol, timeframe, candles)
        return candles

    def _write(self, path: Path, symbol: str, timeframe: str, candles: list[Candle]) -> None:
        payload = {
            "symbol": symbol,
            "timeframe": timeframe,
            "fetched_at": time.time(),
            "candles": [
                {
                    "datetime": c.datetime,
                    "open": c.open,
                    "high": c.high,
                    "low": c.low,
                    "close": c.close,
                    "volume": c.volume,
                }
                for c in candles
            ],
        }
        tmp = path.with_suffix(".json.tmp")
        try:
            tmp.write_text(json.dumps(payload), encoding="utf-8")
            tmp.replace(path)
        except OSError as e:
            logger.warning("Cache write error for %s %s: %s", symbol, timeframe, e)
