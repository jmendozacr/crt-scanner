"""
Unit tests for core/crt_detector.py — Clutifx H4 sweep detection.

Each test builds a minimal OHLCV DataFrame with synthetic H4 candles
that should (or should not) trigger a CRTSetup.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

import pandas as pd
import pytest

from core.crt_detector import detect_crt, CRTSetup

_T0 = datetime(2025, 1, 1, tzinfo=timezone.utc)
PAIR = "EUR_USD"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _c(n: int, o: float, h: float, l: float, c: float, complete: bool = True) -> dict:
    return {
        "time": _T0 + timedelta(hours=4 * n),
        "open": o, "high": h, "low": l, "close": c,
        "volume": 0, "complete": complete,
    }


def _df(*rows: dict) -> pd.DataFrame:
    return pd.DataFrame(list(rows))


# ---------------------------------------------------------------------------
# Basic detection
# ---------------------------------------------------------------------------

class TestBearishCRT:
    def test_bearish_simple(self):
        """sweep.high > ref.high AND sweep.close < ref.high → 1 bearish setup."""
        df = _df(
            _c(0, 1.10, 1.12, 1.09, 1.11),    # ref
            _c(1, 1.11, 1.13, 1.095, 1.115),  # sweep: high=1.13>1.12, close=1.115<1.12, low=1.095>ref.low → only bearish
        )
        result = detect_crt(df, PAIR, lookback=10)
        assert len(result) == 1
        assert result[0].direction == "bearish"
        assert result[0].crt_h == pytest.approx(1.12)
        assert result[0].crt_l == pytest.approx(1.09)

    def test_breakout_not_crt(self):
        """sweep.close > ref.high (breakout, not a sweep) → no bearish setup."""
        df = _df(
            _c(0, 1.10, 1.12, 1.09, 1.11),   # ref
            _c(1, 1.11, 1.13, 1.10, 1.125),   # sweep: close=1.125 > ref.high=1.12
        )
        result = detect_crt(df, PAIR)
        bearish = [s for s in result if s.direction == "bearish"]
        assert bearish == []


class TestBullishCRT:
    def test_bullish_simple(self):
        """sweep.low < ref.low AND sweep.close > ref.low → 1 bullish setup."""
        df = _df(
            _c(0, 1.10, 1.12, 1.09, 1.105),  # ref
            _c(1, 1.10, 1.115, 1.08, 1.095),  # sweep: low=1.08<1.09, close=1.095>1.09
        )
        result = detect_crt(df, PAIR, lookback=10)
        assert len(result) == 1
        assert result[0].direction == "bullish"
        assert result[0].crt_l == pytest.approx(1.09)

    def test_breakout_down_not_crt(self):
        """sweep.close < ref.low (downward breakout) → no bullish setup."""
        df = _df(
            _c(0, 1.10, 1.12, 1.09, 1.105),  # ref
            _c(1, 1.10, 1.115, 1.08, 1.085),  # sweep: close=1.085 < ref.low=1.09
        )
        result = detect_crt(df, PAIR)
        bullish = [s for s in result if s.direction == "bullish"]
        assert bullish == []


# ---------------------------------------------------------------------------
# No signal
# ---------------------------------------------------------------------------

class TestNoSignal:
    def test_no_sweep_no_signal(self):
        """sweep does not exceed any ref extreme → empty list."""
        df = _df(
            _c(0, 1.10, 1.12, 1.09, 1.11),   # ref
            _c(1, 1.10, 1.115, 1.095, 1.11),  # sweep: high < ref.high, low > ref.low
        )
        assert detect_crt(df, PAIR) == []

    def test_too_few_candles(self):
        """Only 1 complete candle → []."""
        df = _df(_c(0, 1.10, 1.12, 1.09, 1.11))
        assert detect_crt(df, PAIR) == []

    def test_empty_dataframe(self):
        """Empty df → []."""
        df = _df()
        assert detect_crt(df, PAIR) == []


# ---------------------------------------------------------------------------
# Incomplete candles
# ---------------------------------------------------------------------------

class TestIncompleteCandlesIgnored:
    def test_incomplete_sweep_not_used(self):
        """If the last candle is incomplete it should NOT be used as sweep_candle."""
        df = _df(
            _c(0, 1.10, 1.12, 1.09, 1.11),            # ref (complete)
            _c(1, 1.11, 1.13, 1.08, 1.115, False),    # incomplete sweep → ignored
        )
        # Only 1 complete candle → []
        assert detect_crt(df, PAIR) == []

    def test_incomplete_ref_not_used(self):
        """Incomplete candles in the window are not evaluated as ref_candle."""
        df = _df(
            _c(0, 1.10, 1.12, 1.09, 1.11, False),    # incomplete ref → ignored
            _c(1, 1.11, 1.13, 1.08, 1.115),           # sweep (only complete)
        )
        # Only 1 complete candle → []
        assert detect_crt(df, PAIR) == []


# ---------------------------------------------------------------------------
# Lookback
# ---------------------------------------------------------------------------

class TestLookback:
    def test_lookback_respected(self):
        """A ref_candle that is exactly outside the lookback window is not detected."""
        # Build 12 neutral candles, ref at index 0, sweep at index 11
        rows = [_c(i, 1.10, 1.105 + i * 0.001, 1.095, 1.10) for i in range(10)]
        # ref_candle at position 0 has high=1.105
        rows[0] = _c(0, 1.10, 1.105, 1.095, 1.10)
        # neutral candles 1-9
        # sweep at position 10 sweeps ref[0].high but ref[0] is outside lookback=9
        rows.append(_c(10, 1.10, 1.11, 1.09, 1.104))  # high=1.11>1.105, close<1.105
        df = _df(*rows)
        # With lookback=9, the window covers candles 1-9 → ref[0] is excluded
        result = detect_crt(df, PAIR, lookback=9)
        bearish = [s for s in result if s.direction == "bearish"
                   and s.crt_h == pytest.approx(1.105)]
        assert bearish == []

    def test_lookback_includes_ref(self):
        """Same setup but with lookback=10 → ref IS included."""
        # rows 1-9 have high=1.115 > sweep.high=1.11 → not swept bearish
        # row 0 has unique high=1.105 → swept bearish only when in window
        rows = [_c(i, 1.10, 1.115, 1.095, 1.10) for i in range(10)]
        rows[0] = _c(0, 1.10, 1.105, 1.095, 1.10)
        rows.append(_c(10, 1.10, 1.11, 1.096, 1.104))  # low=1.096>1.095 → no bullish
        df = _df(*rows)
        result = detect_crt(df, PAIR, lookback=10)
        bearish = [s for s in result if s.direction == "bearish"
                   and s.crt_h == pytest.approx(1.105)]
        assert len(bearish) == 1


# ---------------------------------------------------------------------------
# Multiple setups
# ---------------------------------------------------------------------------

class TestMultipleSetups:
    def test_multiple_refs_both_swept(self):
        """Sweep candle sweeps 2 different ref_candles → 2 setups."""
        df = _df(
            _c(0, 1.10, 1.115, 1.095, 1.11),  # ref A: high=1.115
            _c(1, 1.10, 1.120, 1.095, 1.11),  # ref B: high=1.120
            _c(2, 1.10, 1.125, 1.096, 1.112), # sweep: high=1.125>both, close=1.112<1.115<1.120
        )
        result = detect_crt(df, PAIR, lookback=10)
        bearish = [s for s in result if s.direction == "bearish"]
        assert len(bearish) == 2

    def test_sort_by_proximity(self):
        """Setup whose range midpoint is closest to current price comes first."""
        # sweep_candle at 1.105 midpoint (high=1.11, low=1.10)
        # ref A: range 1.08–1.12, midpoint=1.10 → distance = |1.105-1.10| = 0.005
        # ref B: range 1.06–1.09, midpoint=1.075 → distance = |1.105-1.075| = 0.030
        df = _df(
            _c(0, 1.08, 1.09, 1.06, 1.08),    # ref B: low=1.06, high=1.09
            _c(1, 1.09, 1.12, 1.08, 1.10),    # ref A: high=1.12
            _c(2, 1.10, 1.13, 1.055, 1.085),  # sweep: high=1.13>1.12>1.09; close=1.085<1.09<1.12 → bearish both
        )
        result = detect_crt(df, PAIR, lookback=10)
        # Both refs are bearish-swept; check ordering
        bearish = [s for s in result if s.direction == "bearish"]
        assert len(bearish) == 2
        # ref A (high=1.12, midpoint=1.10) is closer to sweep midpoint=(1.13+1.055)/2=1.0925
        # |1.0925 - 1.10| = 0.0075; |1.0925 - (1.09+1.06)/2| = |1.0925-1.075| = 0.0175
        # ref A should come first
        assert bearish[0].crt_h == pytest.approx(1.12)
        assert bearish[1].crt_h == pytest.approx(1.09)


# ---------------------------------------------------------------------------
# expires_at
# ---------------------------------------------------------------------------

class TestExpiresAt:
    def test_expires_at_is_sweep_plus_4h(self):
        """expires_at == sweep_candle["time"] + 4 hours."""
        df = _df(
            _c(0, 1.10, 1.12, 1.09, 1.11),
            _c(1, 1.11, 1.13, 1.095, 1.115),  # low=1.095>ref.low=1.09 → only bearish
        )
        result = detect_crt(df, PAIR)
        assert len(result) == 1
        sweep_time = _T0 + timedelta(hours=4)  # candle index 1
        assert result[0].expires_at == pd.Timestamp(sweep_time) + pd.Timedelta(hours=4)

    def test_pair_stored_correctly(self):
        """CRTSetup.pair matches the pair argument."""
        df = _df(
            _c(0, 1.10, 1.12, 1.09, 1.11),
            _c(1, 1.11, 1.13, 1.08, 1.115),
        )
        result = detect_crt(df, "GBP_USD")
        assert result[0].pair == "GBP_USD"
