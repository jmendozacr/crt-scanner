"""
In-memory buffer of candles per (pair, granularity), backed by pandas DataFrames.

Usage:
    store = CandleStore(buffer_size=100)
    store.update(candles)                         # ingest list[Candle]
    df = store.get("EUR_USD", "H4")               # DataFrame oldest→newest
    last = store.get_last("EUR_USD", "H4", n=3)   # last N complete candles
"""
from __future__ import annotations

import logging
from collections import defaultdict

import pandas as pd

from data.twelvedata_client import Candle

logger = logging.getLogger(__name__)

# Columns stored in each DataFrame (matches Candle fields minus pair/granularity)
_COLUMNS = ["time", "open", "high", "low", "close", "volume", "complete"]


class CandleStore:
    """Thread-safe (GIL-protected) rolling buffer of OHLCV candles."""

    def __init__(self, buffer_size: int = 100) -> None:
        if buffer_size < 1:
            raise ValueError("buffer_size must be >= 1")
        self._buffer_size = buffer_size
        # (pair, granularity) -> DataFrame
        self._store: dict[tuple[str, str], pd.DataFrame] = defaultdict(
            self._empty_df
        )

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def update(self, candles: list[Candle]) -> None:
        """
        Ingest new candles into the store.

        Duplicate timestamps (same pair + granularity + time) are replaced
        so that in-progress candles that later close are updated correctly.
        """
        # Group by key to minimise DataFrame rebuilds
        groups: dict[tuple[str, str], list[Candle]] = defaultdict(list)
        for c in candles:
            groups[(c.pair, c.granularity)].append(c)

        for key, batch in groups.items():
            new_rows = pd.DataFrame(
                [
                    {
                        "time": c.time,
                        "open": c.open,
                        "high": c.high,
                        "low": c.low,
                        "close": c.close,
                        "volume": c.volume,
                        "complete": c.complete,
                    }
                    for c in batch
                ]
            )
            existing = self._store[key]
            merged = (
                pd.concat([existing, new_rows])
                .drop_duplicates(subset="time", keep="last")
                .sort_values("time")
                .tail(self._buffer_size)
                .reset_index(drop=True)
            )
            self._store[key] = merged
            logger.debug(
                "CandleStore updated %s %s — %d rows", key[0], key[1], len(merged)
            )

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get(self, pair: str, granularity: str) -> pd.DataFrame:
        """Return a copy of all buffered candles (oldest → newest)."""
        return self._store[(pair, granularity)].copy()

    def get_last(
        self,
        pair: str,
        granularity: str,
        n: int = 1,
        *,
        complete_only: bool = True,
    ) -> pd.DataFrame:
        """
        Return the last `n` candles.

        Args:
            n:             Number of candles to return.
            complete_only: When True (default), exclude the currently-open candle.
        """
        df = self._store[(pair, granularity)]
        if complete_only:
            df = df[df["complete"]]
        return df.tail(n).copy()

    def keys(self) -> list[tuple[str, str]]:
        """Return all (pair, granularity) keys that have data."""
        return [k for k, df in self._store.items() if not df.empty]

    def __len__(self) -> int:
        return len(self._store)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _empty_df() -> pd.DataFrame:
        return pd.DataFrame(columns=_COLUMNS)
