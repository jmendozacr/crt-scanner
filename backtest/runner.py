"""
Walk-forward backtest simulation for the CRT scanner (Clutifx model).
"""
from __future__ import annotations

import asyncio
import logging

import pandas as pd

from config import MinScore
from core.crt_detector import detect_crt
from core.entry_model import find_engulfing_ob
from core.htf_confluence import get_key_levels
from data.candle_store import CandleStore
from data.twelvedata_client import TwelveDataClient
from main import _check_setup_confluence

from backtest.evaluator import TradeResult, evaluate_setup_trade

logger = logging.getLogger(__name__)

_RATE_LIMIT_SLEEP = 8.0   # seconds between get_candles calls (8 req/min free tier)
_CANDLE_COUNTS: dict[str, int] = {"D": 200, "H4": 5000, "M15": 5000}


async def bootstrap_backtest(
    client: TwelveDataClient,
    store: CandleStore,
    pairs: list[str],
) -> None:
    """
    Fetch historical candles (D / H4 / M15) for each pair.
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
    Walk-forward simulation across all pairs using the Clutifx model.

    For each H4 candle position i:
      1. Call detect_crt on the slice h4[:i+1] — finds setups on the last candle.
      2. Run HTF confluence check; skip if min_score=A and no level found.
      3. Call find_engulfing_ob on M15 candles in the sweep window.
      4. Scan subsequent M15 candles for OB touch or invalidation.
      5. Evaluate trade outcome (WIN / LOSS / OPEN).

    Returns a list of TradeResult (OPEN trades excluded).
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

        # Fetch key levels once per pair (Daily candles are static for the backtest)
        key_levels = get_key_levels(store, pair)

        # Walk forward through complete H4 candles
        complete = h4_df[h4_df["complete"]].reset_index(drop=True)

        for i in range(1, len(complete)):
            slice_df = complete.iloc[:i + 1].copy()
            setups = detect_crt(slice_df, pair)
            if not setups:
                continue

            for setup in setups:
                sweep_time = setup.sweep_candle["time"]

                if not (m15_start <= sweep_time <= m15_end):
                    continue

                dedup_key = (pair, sweep_time, setup.direction)
                if dedup_key in seen:
                    continue

                # HTF confluence filter
                level = _check_setup_confluence(setup, key_levels)
                if min_score == MinScore.A and level is None:
                    continue
                setup.htf_level = level

                # Find OB in M15 during H4 sweep window
                ob = find_engulfing_ob(m15_df, setup)
                if ob is None:
                    continue

                seen.add(dedup_key)

                # Scan M15 candles after OB: invalidation beats touch
                after_ob = m15_df[m15_df["time"] > ob.formed_at].reset_index(drop=True)
                if after_ob.empty:
                    continue

                touch_idx: int | None = None
                for idx, row in after_ob.iterrows():
                    close = float(row["close"])
                    high  = float(row["high"])
                    low   = float(row["low"])

                    if setup.direction == "bearish":
                        if close > ob.high:
                            touch_idx = None; break   # invalidated
                        if high >= ob.low:
                            touch_idx = idx; break    # touched
                    else:
                        if close < ob.low:
                            touch_idx = None; break   # invalidated
                        if low <= ob.high:
                            touch_idx = idx; break    # touched

                if touch_idx is None:
                    continue

                future = after_ob.loc[touch_idx:].reset_index(drop=True)
                if future.empty:
                    continue

                result = evaluate_setup_trade(setup, ob, future, rr)
                if result.outcome == "OPEN":
                    continue   # no future data — unresolved

                results.append(result)
                logger.debug(
                    "%s | %s | entry=%.5f sl=%.5f tp=%.5f → %s",
                    pair, setup.direction,
                    result.entry_price, result.sl_price, result.tp_price,
                    result.outcome,
                )

    return results
