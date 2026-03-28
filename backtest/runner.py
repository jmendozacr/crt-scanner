"""
Walk-forward backtest simulation for the CRT scanner.
"""
from __future__ import annotations

import asyncio
import logging

from config import MinScore
from core.crt_detector import detect
from core.entry_models import find_entry
from core.htf_confluence import run_confluence
from data.candle_store import CandleStore
from data.twelvedata_client import TwelveDataClient
from main import _passes_filter

from backtest.evaluator import TradeResult, evaluate_trade

logger = logging.getLogger(__name__)

_RATE_LIMIT_SLEEP = 8.0   # seconds between get_candles calls (8 req/min free tier)
# Per-granularity counts:
#   D   — 200 candles; enough for recent key levels, avoids thousands of FVG/OB hits
#   H4  — 5000 candles ≈ 2 years; provides a large pool of historical signals
#   M15 — 5000 candles ≈ 52 days; defines the backtest evaluation window
_CANDLE_COUNTS: dict[str, int] = {"D": 200, "H4": 5000, "M15": 5000}


async def bootstrap_backtest(
    client: TwelveDataClient,
    store: CandleStore,
    pairs: list[str],
) -> None:
    """
    Fetch _CANDLE_COUNT candles of D + H4 + M15 for each pair.
    Sleeps 8s between every request to stay within the free-tier rate limit.
    """
    granularities = ("D", "H4", "M15")
    total = len(pairs) * len(granularities)
    count = 0

    logger.info(
        "Bootstrap started — %d pair(s) × 3 granularities (%d requests, est. %ds)",
        len(pairs), total, (total - 1) * int(_RATE_LIMIT_SLEEP),
    )

    for pair in pairs:
        for gran in granularities:
            try:
                candles = await client.get_candles(pair, gran, count=_CANDLE_COUNTS[gran])
                store.update(candles)
            except Exception as exc:
                logger.warning("Bootstrap failed for %s %s: %s", pair, gran, exc)
            count += 1
            if count < total:
                await asyncio.sleep(_RATE_LIMIT_SLEEP)
        logger.info("Bootstrap complete for %s", pair)

    logger.info("Bootstrap finished — store ready")


async def run_backtest(
    store: CandleStore,
    pairs: list[str],
    min_score: MinScore,
    rr: float,
) -> list[TradeResult]:
    """
    Walk-forward simulation across all pairs.

    For each H4 CRT signal:
      1. Checks that the signal falls within the available M15 data window.
      2. Slices M15 to candles that existed at signal time (no look-ahead).
      3. Runs find_entry() on the slice.
      4. Evaluates the trade outcome against subsequent M15 candles.

    Returns a list of TradeResult (WIN, LOSS — OPEN trades with no future data excluded).
    """
    results: list[TradeResult] = []
    seen: set[tuple] = set()   # dedup: (pair, sweep_time, direction)

    for pair in pairs:
        h4_df  = store.get(pair, "H4")
        m15_df = store.get(pair, "M15")

        if h4_df.empty or m15_df.empty:
            logger.warning("No data for %s — skipping", pair)
            continue

        m15_start = m15_df["time"].min()
        m15_end   = m15_df["time"].max()
        logger.info(
            "%s M15 coverage: %s → %s",
            pair,
            m15_start.strftime("%Y-%m-%d"),
            m15_end.strftime("%Y-%m-%d"),
        )

        signals = detect(h4_df, pair, "H4")
        if not signals:
            continue

        # Pre-filter to M15 coverage window BEFORE running confluence.
        # This avoids processing thousands of historical signals that can
        # never produce a trade result (no M15 data to find entries or
        # evaluate outcomes).
        in_window = [
            s for s in signals
            if m15_start <= s.sweep_time <= m15_end
        ]
        if not in_window:
            logger.info("%s: no signals within M15 window — skipping", pair)
            continue
        logger.info("%s: %d signal(s) in M15 window (of %d total)", pair, len(in_window), len(signals))

        confluence_results = run_confluence(in_window, store, pair)

        for conf in confluence_results:
            if not _passes_filter(conf, min_score):
                continue

            sweep_time = conf.signal.sweep_time

            # Time-slice M15 to prevent look-ahead bias.
            # Use tail(100) to mirror the live scanner's buffer_size=100,
            # keeping detector performance in line with production.
            m15_at_signal = m15_df[m15_df["time"] <= sweep_time].tail(100)
            if len(m15_at_signal) < 3:
                continue

            entry = find_entry(conf, m15_at_signal)
            if entry is None:
                continue

            # Dedup: one result per (pair, sweep_time, direction)
            dedup_key = (pair, sweep_time, conf.signal.direction)
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            future = m15_df[m15_df["time"] > entry.time].reset_index(drop=True)
            if len(future) == 0:
                # Signal is at the very edge of available data — skip (unresolved)
                continue

            result = evaluate_trade(entry, future, rr)
            results.append(result)
            logger.debug(
                "%s | %s | %s | entry=%.5f sl=%.5f tp=%.5f → %s",
                pair, entry.entry_model.value,
                conf.signal.direction.value,
                result.entry_price, result.sl_price, result.tp_price,
                result.outcome,
            )

    return results
