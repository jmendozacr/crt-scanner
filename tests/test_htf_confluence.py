"""Tests for core/htf_confluence.py"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from core.htf_confluence import check_confluence
from core.models import (
    CRTModel, CRTSignal, Direction, KeyLevel, KeyLevelType, Score,
)

_T0 = datetime(2025, 1, 1, tzinfo=timezone.utc)

PAIR = "EUR_USD"


def _signal(direction: Direction, crt_high: float, crt_low: float) -> CRTSignal:
    return CRTSignal(
        model=CRTModel.TWO_CANDLE,
        direction=direction,
        crt_high=crt_high,
        crt_low=crt_low,
        ref_time=_T0,
        sweep_time=_T0 + timedelta(hours=4),
        pair=PAIR,
        granularity="H4",
    )


def _kl(direction: Direction, low: float, high: float,
        kl_type: KeyLevelType = KeyLevelType.FVG) -> KeyLevel:
    return KeyLevel(
        type=kl_type,
        direction=direction,
        low=low,
        high=high,
        time=_T0,
        pair=PAIR,
        granularity="D",
    )


class TestCheckConfluence:
    def test_bullish_crt_with_bullish_fvg(self):
        """Bullish CRT low falls inside a bullish Daily FVG → Score A."""
        signal = _signal(Direction.BULLISH, crt_high=1.12, crt_low=1.08)
        # FVG zone 1.07–1.09 contains crt_low=1.08 ✓
        kl = _kl(Direction.BULLISH, low=1.07, high=1.09)
        result = check_confluence(signal, [kl], tolerance_ratio=0.0)
        assert result.aligned is True
        assert result.score == Score.A
        assert result.key_level == kl

    def test_bearish_crt_with_bearish_ob(self):
        """Bearish CRT high falls inside a bearish Daily OB → Score A."""
        signal = _signal(Direction.BEARISH, crt_high=1.14, crt_low=1.10)
        # OB zone 1.13–1.15 contains crt_high=1.14 ✓
        kl = _kl(Direction.BEARISH, low=1.13, high=1.15, kl_type=KeyLevelType.ORDER_BLOCK)
        result = check_confluence(signal, [kl], tolerance_ratio=0.0)
        assert result.aligned is True
        assert result.score == Score.A

    def test_no_confluence_returns_score_b(self):
        """Key level far away → Score B."""
        signal = _signal(Direction.BULLISH, crt_high=1.12, crt_low=1.08)
        kl = _kl(Direction.BULLISH, low=1.04, high=1.05)  # too low
        result = check_confluence(signal, [kl], tolerance_ratio=0.0)
        assert result.aligned is False
        assert result.score == Score.B
        assert result.key_level is None

    def test_direction_mismatch_no_confluence(self):
        """Bullish CRT against bearish key level → no confluence."""
        signal = _signal(Direction.BULLISH, crt_high=1.12, crt_low=1.08)
        kl = _kl(Direction.BEARISH, low=1.07, high=1.09)  # right price, wrong dir
        result = check_confluence(signal, [kl], tolerance_ratio=0.0)
        assert result.aligned is False

    def test_tolerance_allows_nearby_level(self):
        """CRT low just outside key level, but within tolerance → Score A."""
        signal = _signal(Direction.BULLISH, crt_high=1.12, crt_low=1.08)
        # crt_low=1.08, key level 1.085–1.09 (crt_low is 0.005 below key.low)
        # crt_range=0.04, tol=0.1*0.04=0.004 — too small to bridge 0.005
        kl = _kl(Direction.BULLISH, low=1.085, high=1.09)
        result_strict = check_confluence(signal, [kl], tolerance_ratio=0.0)
        assert result_strict.aligned is False

        # With tolerance_ratio=0.2: tol=0.2*0.04=0.008 > 0.005 → aligned
        result_tol = check_confluence(signal, [kl], tolerance_ratio=0.2)
        assert result_tol.aligned is True

    def test_most_recent_key_level_wins(self):
        """When multiple key levels match, the most recent one is returned."""
        signal = _signal(Direction.BULLISH, crt_high=1.12, crt_low=1.08)
        kl_old = KeyLevel(KeyLevelType.FVG, Direction.BULLISH, 1.09, 1.07, _T0, PAIR, "D")
        kl_new = KeyLevel(KeyLevelType.FVG, Direction.BULLISH, 1.09, 1.07,
                          _T0 + timedelta(days=5), PAIR, "D")
        result = check_confluence(signal, [kl_old, kl_new], tolerance_ratio=0.0)
        assert result.key_level == kl_new

    def test_empty_key_levels(self):
        signal = _signal(Direction.BULLISH, crt_high=1.12, crt_low=1.08)
        result = check_confluence(signal, [], tolerance_ratio=0.0)
        assert result.score == Score.B
        assert result.aligned is False
