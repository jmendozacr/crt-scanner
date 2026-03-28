"""
Twelve Data REST client — async, typed.

Public API (same interface as the original OANDA client):
    get_candles(pair, granularity, count)                          -> list[Candle]
    poll_candles(pairs, granularities, callback, interval_seconds) -> None (runs forever)

Pairs use underscore notation internally (EUR_USD) and are converted to
slash notation (EUR/USD) only when talking to the Twelve Data API.

Granularities use the internal notation (M15, H4, D) and are mapped to
Twelve Data's notation (15min, 4h, 1day) on the way out.

Rate limits (free tier):
    8 requests / minute · 800 credits / day
    poll_candles uses batch requests (all pairs in one call per granularity)
    to stay well within these limits — 3 req/cycle instead of 27.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Awaitable, Callable

import aiohttp

from config import Settings

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.twelvedata.com"

# Internal granularity → Twelve Data interval string
_GRANULARITY_MAP: dict[str, str] = {
    "M1":  "1min",
    "M5":  "5min",
    "M15": "15min",
    "M30": "30min",
    "H1":  "1h",
    "H4":  "4h",
    "D":   "1day",
    "W":   "1week",
}

# Internal granularity → duration in seconds (for complete-candle inference and poll timing)
GRANULARITY_SECONDS: dict[str, int] = {
    "M1":  60,
    "M5":  300,
    "M15": 900,
    "M30": 1800,
    "H1":  3600,
    "H4":  14400,
    "D":   86400,
    "W":   604800,
}


def _to_td_symbol(pair: str) -> str:
    """EUR_USD  →  EUR/USD"""
    return pair.replace("_", "/")


def _to_internal_pair(symbol: str) -> str:
    """EUR/USD  →  EUR_USD"""
    return symbol.replace("/", "_")


def _is_complete(candle_time: datetime, granularity: str) -> bool:
    """
    Twelve Data does not provide a 'complete' flag.
    A candle that opened at T with interval I is complete when now >= T + I.
    """
    interval = timedelta(seconds=GRANULARITY_SECONDS[granularity])
    return datetime.now(timezone.utc) >= candle_time + interval


@dataclass(frozen=True, slots=True)
class Candle:
    pair: str          # EUR_USD
    granularity: str   # H4
    time: datetime     # UTC, timezone-aware
    open: float
    high: float
    low: float
    close: float
    volume: int        # Twelve Data returns 0 for Forex — kept for interface parity
    complete: bool

    def __repr__(self) -> str:
        direction = "▲" if self.close >= self.open else "▼"
        return (
            f"Candle({self.pair} {self.granularity} {direction} "
            f"O={self.open} H={self.high} L={self.low} C={self.close} "
            f"@ {self.time.isoformat()} complete={self.complete})"
        )


CandleCallback = Callable[[list[Candle]], Awaitable[None]]


class TwelveDataClient:
    """Async wrapper around the Twelve Data v1 REST API."""

    def __init__(self, settings: Settings) -> None:
        self._api_key = settings.twelvedata_api_key
        self._session: aiohttp.ClientSession | None = None

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "TwelveDataClient":
        self._session = aiohttp.ClientSession(
            base_url=_BASE_URL,
            timeout=aiohttp.ClientTimeout(total=30),
        )
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._session:
            await self._session.close()
            self._session = None

    def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            raise RuntimeError(
                "TwelveDataClient must be used as an async context manager: "
                "`async with TwelveDataClient(settings) as client:`"
            )
        return self._session

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    async def get_candles_batch(
        self,
        pairs: list[str],
        granularity: str,
        count: int = 100,
    ) -> dict[str, list[Candle]]:
        """
        Fetch the last `count` candles for multiple pairs in a single request.

        Returns a dict keyed by internal pair name (EUR_USD).
        """
        if granularity not in _GRANULARITY_MAP:
            raise ValueError(
                f"Unknown granularity '{granularity}'. "
                f"Valid values: {list(_GRANULARITY_MAP)}"
            )
        return await self._fetch_time_series(pairs, granularity, count=count)

    async def get_candles(
        self,
        pair: str,
        granularity: str,
        count: int = 100,
    ) -> list[Candle]:
        """
        Fetch the last `count` candles for `pair` at `granularity`.

        Args:
            pair:        Internal pair name, e.g. "EUR_USD".
            granularity: Internal granularity, e.g. "H4", "M15", "D".
            count:       Number of candles to retrieve (Twelve Data max: 5000).

        Returns:
            List of Candle ordered oldest → newest.
            The last candle may be incomplete (complete=False) if its interval
            has not elapsed yet.
        """
        if granularity not in _GRANULARITY_MAP:
            raise ValueError(
                f"Unknown granularity '{granularity}'. "
                f"Valid values: {list(_GRANULARITY_MAP)}"
            )

        raw = await self._fetch_time_series(
            symbols=[pair],
            granularity=granularity,
            count=count,
        )
        return raw.get(pair, [])

    async def poll_candles(
        self,
        pairs: list[str],
        granularities: list[str],
        callback: CandleCallback,
        *,
        interval_seconds: int | None = None,
    ) -> None:
        """
        Continuously poll Twelve Data for closed candles and invoke `callback`
        with any newly completed candles.

        Uses batch requests (all pairs in a single call per granularity) to
        minimise API credit usage — 3 requests/cycle for 3 TFs regardless of
        the number of pairs.

        Args:
            pairs:            List of internal pair names (e.g. ["EUR_USD", "GBP_USD"]).
            granularities:    List of internal granularity strings.
            callback:         Async callable receiving list[Candle] of *newly closed* candles.
            interval_seconds: Override poll interval; defaults to the smallest granularity.

        Runs indefinitely until cancelled.
        """
        for g in granularities:
            if g not in _GRANULARITY_MAP:
                raise ValueError(f"Unknown granularity '{g}'.")

        poll_interval = interval_seconds or min(
            GRANULARITY_SECONDS[g] for g in granularities
        )

        # Seed: record the latest closed-candle timestamp per (pair, granularity)
        last_seen: dict[tuple[str, str], datetime] = {}
        for gran in granularities:
            batch = await self._fetch_time_series(pairs, gran, count=2)
            for pair, candles in batch.items():
                closed = [c for c in candles if c.complete]
                if closed:
                    last_seen[(pair, gran)] = closed[-1].time

        logger.info(
            "Polling started — pairs=%s granularities=%s interval=%ds",
            pairs,
            granularities,
            poll_interval,
        )

        while True:
            await asyncio.sleep(poll_interval)
            new_candles: list[Candle] = []

            for gran in granularities:
                try:
                    # One request for ALL pairs at this granularity
                    batch = await self._fetch_time_series(pairs, gran, count=5)
                    for pair, candles in batch.items():
                        closed = [c for c in candles if c.complete]
                        key = (pair, gran)
                        cutoff = last_seen.get(key)
                        fresh = (
                            [c for c in closed if c.time > cutoff]
                            if cutoff
                            else closed
                        )
                        if fresh:
                            last_seen[key] = fresh[-1].time
                            new_candles.extend(fresh)
                            logger.debug(
                                "%d new candle(s) — %s %s", len(fresh), pair, gran
                            )
                except Exception as exc:
                    logger.error("Poll error granularity=%s: %s", gran, exc)

            if new_candles:
                try:
                    await callback(new_candles)
                except Exception as exc:
                    logger.error("Callback raised: %s", exc)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _fetch_time_series(
        self,
        symbols: list[str],
        granularity: str,
        count: int,
    ) -> dict[str, list[Candle]]:
        """
        Call /time_series for one or more symbols in a single HTTP request.

        Returns a dict keyed by internal pair name (EUR_USD).
        """
        session = self._get_session()
        td_symbols = ",".join(_to_td_symbol(p) for p in symbols)
        td_interval = _GRANULARITY_MAP[granularity]

        params = {
            "symbol":     td_symbols,
            "interval":   td_interval,
            "outputsize": str(count),
            "timezone":   "UTC",
            "apikey":     self._api_key,
        }

        logger.debug("GET /time_series symbols=%s interval=%s", td_symbols, td_interval)

        async with session.get("/time_series", params=params) as resp:
            resp.raise_for_status()
            data: dict = await resp.json()  # type: ignore[type-arg]

        if "status" in data and data["status"] == "error":
            raise RuntimeError(f"Twelve Data API error: {data.get('message', data)}")

        return self._parse_response(data, symbols, granularity)

    def _parse_response(
        self,
        data: dict,  # type: ignore[type-arg]
        requested_pairs: list[str],
        granularity: str,
    ) -> dict[str, list[Candle]]:
        """
        Twelve Data returns different shapes for single vs. multiple symbols:
          Single:  { "meta": {...}, "values": [...], "status": "ok" }
          Batch:   { "EUR/USD": { "meta": {...}, "values": [...] }, "GBP/USD": {...} }
        """
        result: dict[str, list[Candle]] = {}

        if "values" in data:
            # Single-symbol response
            pair = requested_pairs[0]
            result[pair] = self._parse_values(data["values"], pair, granularity)
        else:
            # Batch response keyed by TD symbol (EUR/USD)
            for td_symbol, payload in data.items():
                if not isinstance(payload, dict) or "values" not in payload:
                    continue
                pair = _to_internal_pair(td_symbol)
                result[pair] = self._parse_values(payload["values"], pair, granularity)

        return result

    @staticmethod
    def _parse_values(
        values: list[dict],  # type: ignore[type-arg]
        pair: str,
        granularity: str,
    ) -> list[Candle]:
        """
        Parse the 'values' array from Twelve Data.

        Twelve Data returns candles newest → oldest; we reverse to oldest → newest.
        The 'complete' flag is inferred from elapsed time since candle open.
        """
        candles: list[Candle] = []
        for row in reversed(values):  # oldest → newest
            candle_time = datetime.fromisoformat(row["datetime"]).replace(
                tzinfo=timezone.utc
            )
            candles.append(
                Candle(
                    pair=pair,
                    granularity=granularity,
                    time=candle_time,
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=int(float(row.get("volume") or 0)),
                    complete=_is_complete(candle_time, granularity),
                )
            )
        return candles
