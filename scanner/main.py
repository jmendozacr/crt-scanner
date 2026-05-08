from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime, timedelta, timezone

from scanner.alerts import AlertDeliveryError, format_alert, send_alert
from scanner.config import settings
from scanner.config.pairs import PAIRS, SYMBOLS, Pair
from scanner.data.cache import CandleCache
from scanner.data.fetcher import FetcherError, TwelveDataFetcher
from scanner.detectors import (
    check_smt,
    detect_tbs,
    detect_model1,
    detect_turtle_soup,
)
from scanner.state.tracker import AlertTracker
from scanner.utils.sessions import get_session

logger = logging.getLogger(__name__)

_TS_FMT = "%Y-%m-%d %H:%M:%S"
_WINDOW_FMT = "%Y-%m-%d %H:%M"


def scan_pair(pair: Pair, cache: CandleCache, tracker: AlertTracker) -> None:
    symbol = pair.symbol

    # Step 1 — lazy expiry cleanup
    tracker.clear_if_expired(symbol)

    # Step 2 — skip if already active
    if tracker.is_active(symbol):
        logger.debug("Skipping %s — alert window still active", symbol)
        return

    # Step 3 — H4 Turtle Soup (bias derived internally)
    h4_candles = cache.get(symbol, settings.H4_TIMEFRAME)
    ts = detect_turtle_soup(h4_candles)
    if ts is None:
        logger.debug("No Turtle Soup for %s", symbol)
        return

    # Step 4 — session (informational only — no longer a hard gate)
    session = get_session(ts.ts_candle_datetime)

    # Step 5 — parse window_start, compute window_end
    try:
        window_start_dt = datetime.strptime(ts.window_start, _TS_FMT)
    except ValueError:
        window_start_dt = datetime.strptime(ts.window_start, _WINDOW_FMT)
    window_end_dt = window_start_dt + timedelta(hours=4)
    window_start_str = window_start_dt.strftime(_WINDOW_FMT)
    window_end_str = window_end_dt.strftime(_WINDOW_FMT)

    # Step 6 — M15 TBS
    m15_candles = cache.get(symbol, settings.M15_TIMEFRAME)
    tbs = detect_tbs(m15_candles, ts.bias, window_start_str, window_end_str)
    if tbs is None:
        logger.debug("No TBS for %s", symbol)
        return

    # Step 7 — M15 Model #1
    model1 = detect_model1(
        m15_candles,
        ts.bias,
        tbs.tbs_candle_datetime,
        window_end_str,
    )
    if model1 is None:
        logger.debug("No Model #1 for %s", symbol)
        return

    # Step 8 — SMT divergence check (optional — skipped when no partner defined)
    smt = None
    if pair.smt_partner is not None:
        partner_candles = cache.get(pair.smt_partner, settings.M15_TIMEFRAME)
        smt = check_smt(
            m15_candles,
            partner_candles,
            bias=ts.bias,
            primary_symbol=symbol,
            partner_symbol=pair.smt_partner,
            correlation=pair.smt_correlation,
        )

    # Step 9 — format and send alert
    message = format_alert(symbol, ts, model1, smt, session=session)
    try:
        send_alert(message)
    except AlertDeliveryError as e:
        logger.warning("Alert delivery failed for %s: %s", symbol, e.reason)
        return

    # Step 10 — mark alerted only after successful delivery
    tracker.mark_alerted(symbol, window_start_dt, window_end_dt)
    logger.info(
        "Alert sent for %s — window %s to %s", symbol, window_start_str, window_end_str
    )


def run_scan(
    cache: CandleCache,
    tracker: AlertTracker,
    pairs: list[Pair] | None = None,
) -> None:
    _pairs = pairs if pairs is not None else PAIRS
    for pair in _pairs:
        try:
            scan_pair(pair, cache, tracker)
        except FetcherError as e:
            logger.error("Fetch error for %s: %s", pair.symbol, e)
        except Exception as e:
            logger.exception("Unexpected error for %s: %s", pair.symbol, e)


def _seconds_to_next_m15() -> float:
    now = datetime.now(timezone.utc)
    elapsed = (now.minute % 15) * 60 + now.second + now.microsecond / 1e6
    return max(900.0 - elapsed, 1.0)


def main() -> None:
    parser = argparse.ArgumentParser(description="CRT Scanner")
    parser.add_argument(
        "--pair",
        metavar="SYMBOL",
        default=None,
        help="Scan only this pair (default: all pairs)",
    )
    args = parser.parse_args()

    selected_pairs: list[Pair] | None = None
    if args.pair is not None:
        normalized = args.pair.strip().upper()
        if normalized not in SYMBOLS:
            print(
                f"Error: '{args.pair}' is not a valid pair. "
                f"Valid pairs: {', '.join(SYMBOLS)}",
                file=sys.stderr,
            )
            sys.exit(1)
        selected_pairs = [p for p in PAIRS if p.symbol == normalized]

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )

    fetcher = TwelveDataFetcher(api_key=settings.TWELVE_DATA_API_KEY)
    cache = CandleCache(fetcher)
    tracker = AlertTracker()

    while True:
        logger.info("Starting scan cycle")
        run_scan(cache, tracker, selected_pairs)
        wait = _seconds_to_next_m15()
        logger.info("Next scan in %.1f seconds", wait)
        time.sleep(wait)


if __name__ == "__main__":
    main()
