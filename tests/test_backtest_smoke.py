from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path

import pytest

from scanner.data.candle import Candle
from scripts.backtest_data import _cache_path


def _write_cache(tmp_path: Path, symbol: str, tf: str, n_candles: int) -> None:
    from datetime import datetime, timedelta

    base = datetime(2020, 1, 1)
    candles = [
        Candle(
            datetime=(base + timedelta(days=i)).strftime("%Y-%m-%d %H:%M:%S"),
            open=1.1,
            high=1.2,
            low=1.0,
            close=1.15,
            volume=100.0,
        )
        for i in range(n_candles)
    ]
    path = _cache_path(symbol, tf, tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "symbol": symbol,
                "timeframe": tf,
                "outputsize": n_candles,
                "fetched_at": "2024-01-01T00:00:00+00:00",
                "candles": [dataclasses.asdict(c) for c in candles],
            }
        ),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Smoke: missing cache with --no-fetch exits with code 2
# ---------------------------------------------------------------------------


def test_smoke_no_fetch_missing_cache_exits_2(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["backtest.py", "--no-fetch", "--pairs", "FAKE/PAIR"])

    from scripts.backtest import main

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 2


# ---------------------------------------------------------------------------
# Smoke: --csv flag creates output file
# ---------------------------------------------------------------------------


def test_smoke_csv_flag_creates_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    csv_path = tmp_path / "out.csv"
    symbol = "EUR/USD"

    # Write caches for all 3 timeframes.
    # outputsize must be >= the CLI default (2000) so the stale check passes.
    n = 2000
    for tf in ["1day", "4h", "15min"]:
        _write_cache(tmp_path, symbol, tf, n)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "backtest.py",
            "--no-fetch",
            "--pairs", symbol,
            "--csv", str(csv_path),
            "--min-history", "1",
        ],
    )

    # Patch fetch_and_cache and load_candles to use tmp_path as cache_dir
    import scripts.backtest_data as bd

    original_fetch_and_cache = bd.fetch_and_cache
    original_load_candles = bd.load_candles

    def patched_fetch_and_cache(sym, tf, outputsize, fetcher, cache_dir=None, no_fetch=False):  # type: ignore[override]
        return original_fetch_and_cache(sym, tf, outputsize, fetcher, cache_dir=tmp_path, no_fetch=no_fetch)

    def patched_load_candles(sym, tf, cache_dir=None):  # type: ignore[override]
        return original_load_candles(sym, tf, cache_dir=tmp_path)

    monkeypatch.setattr(bd, "fetch_and_cache", patched_fetch_and_cache)
    monkeypatch.setattr(bd, "load_candles", patched_load_candles)

    # Also patch in backtest.py's imported namespace
    import scripts.backtest as bt

    monkeypatch.setattr(bt, "fetch_and_cache", patched_fetch_and_cache)
    monkeypatch.setattr(bt, "load_candles", patched_load_candles)

    from scripts.backtest import main

    main()

    assert csv_path.exists()
