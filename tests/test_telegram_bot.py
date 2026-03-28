"""Tests for output/telegram_bot.py — format_alert() only (no HTTP)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from core.models import (
    CRTModel, CRTSignal, Direction, ConfluenceResult,
    EntryModel, EntrySignal, KeyLevel, KeyLevelType, Score,
)
from output.telegram_bot import format_alert

_T0 = datetime(2026, 3, 27, 17, 45, tzinfo=timezone.utc)
PAIR = "EUR_USD"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_signal(direction: Direction) -> CRTSignal:
    return CRTSignal(
        model=CRTModel.TWO_CANDLE,
        direction=direction,
        crt_high=1.09200,
        crt_low=1.08100,
        ref_time=_T0,
        sweep_time=_T0 + timedelta(hours=4),
        pair=PAIR,
        granularity="H4",
    )


def _make_kl(direction: Direction, kl_type: KeyLevelType = KeyLevelType.FVG) -> KeyLevel:
    return KeyLevel(kl_type, direction, 1.09200, 1.08100, _T0, PAIR, "D")


def _make_confluence(
    direction: Direction,
    score: Score = Score.A,
    kl_type: KeyLevelType = KeyLevelType.FVG,
    include_kl: bool = True,
) -> ConfluenceResult:
    kl = _make_kl(direction, kl_type) if include_kl else None
    return ConfluenceResult(
        signal=_make_signal(direction),
        key_level=kl,
        score=score,
        aligned=include_kl,
    )


def _make_entry(
    direction: Direction = Direction.BULLISH,
    entry_model: EntryModel = EntryModel.ORDER_BLOCK,
    score: Score = Score.A,
    kl_type: KeyLevelType = KeyLevelType.FVG,
    include_kl: bool = True,
) -> EntrySignal:
    return EntrySignal(
        confluence=_make_confluence(direction, score, kl_type, include_kl),
        entry_model=entry_model,
        entry_zone_low=1.08500,
        entry_zone_high=1.09000,
        time=_T0,
        pair=PAIR,
    )


@pytest.fixture
def bull_entry() -> EntrySignal:
    """Score A, BULLISH, OB model, key_level=FVG D."""
    return _make_entry(Direction.BULLISH, EntryModel.ORDER_BLOCK, Score.A)


@pytest.fixture
def bear_entry() -> EntrySignal:
    """Score A, BEARISH, FVG model, key_level=FVG D."""
    return _make_entry(Direction.BEARISH, EntryModel.FVG, Score.A)


@pytest.fixture
def score_b_entry() -> EntrySignal:
    """Score B, BULLISH, TWS model, key_level=None."""
    return _make_entry(Direction.BULLISH, EntryModel.TURTLE_SOUP_WICK, Score.B, include_kl=False)


# ---------------------------------------------------------------------------
# Pair and direction
# ---------------------------------------------------------------------------

class TestPairAndDirection:
    def test_pair_slash_form_present(self, bull_entry):
        """'EUR/USD' (slash form) appears in formatted message."""
        assert "EUR/USD" in format_alert(bull_entry)

    def test_pair_underscore_absent(self, bull_entry):
        """Raw underscore form 'EUR_USD' does NOT appear (Markdown safety)."""
        assert "EUR_USD" not in format_alert(bull_entry)

    def test_bullish_arrow(self, bull_entry):
        """▲ appears for BULLISH entry."""
        assert "▲" in format_alert(bull_entry)

    def test_bearish_arrow(self, bear_entry):
        """▼ appears for BEARISH entry."""
        assert "▼" in format_alert(bear_entry)

    def test_no_bearish_arrow_in_bullish(self, bull_entry):
        """▼ does NOT appear in a BULLISH alert."""
        assert "▼" not in format_alert(bull_entry)

    def test_no_bullish_arrow_in_bearish(self, bear_entry):
        """▲ does NOT appear in a BEARISH alert."""
        assert "▲" not in format_alert(bear_entry)


# ---------------------------------------------------------------------------
# Score
# ---------------------------------------------------------------------------

class TestScore:
    def test_score_a_present(self, bull_entry):
        """'Score A' appears in message for Score.A entry."""
        assert "Score A" in format_alert(bull_entry)

    def test_score_b_present(self, score_b_entry):
        """'Score B' appears in message for Score.B entry."""
        assert "Score B" in format_alert(score_b_entry)


# ---------------------------------------------------------------------------
# Entry model
# ---------------------------------------------------------------------------

class TestEntryModel:
    def test_ob_model_name(self, bull_entry):
        """'OB' appears when entry_model is ORDER_BLOCK."""
        assert "OB" in format_alert(bull_entry)

    def test_fvg_model_name(self, bear_entry):
        """'FVG' appears when entry_model is FVG."""
        assert "FVG" in format_alert(bear_entry)

    def test_breaker_block_name(self):
        """'Breaker Block' appears when entry_model is BREAKER_BLOCK."""
        entry = _make_entry(entry_model=EntryModel.BREAKER_BLOCK)
        assert "Breaker Block" in format_alert(entry)

    def test_tws_name(self, score_b_entry):
        """'TWS' appears when entry_model is TURTLE_SOUP_WICK."""
        assert "TWS" in format_alert(score_b_entry)

    def test_tbs_name(self):
        """'TBS' appears when entry_model is TURTLE_SOUP_BODY."""
        entry = _make_entry(entry_model=EntryModel.TURTLE_SOUP_BODY)
        assert "TBS" in format_alert(entry)


# ---------------------------------------------------------------------------
# Entry zone prices
# ---------------------------------------------------------------------------

class TestEntryZone:
    def test_zone_low_present(self, bull_entry):
        """entry_zone_low formatted to 5 decimals appears."""
        assert "1.08500" in format_alert(bull_entry)

    def test_zone_high_present(self, bull_entry):
        """entry_zone_high formatted to 5 decimals appears."""
        assert "1.09000" in format_alert(bull_entry)


# ---------------------------------------------------------------------------
# CRT H4 range
# ---------------------------------------------------------------------------

class TestCRTRange:
    def test_crt_high_present(self, bull_entry):
        """crt_high to 5 decimals appears."""
        assert "1.09200" in format_alert(bull_entry)

    def test_crt_low_present(self, bull_entry):
        """crt_low to 5 decimals appears."""
        assert "1.08100" in format_alert(bull_entry)


# ---------------------------------------------------------------------------
# Key level
# ---------------------------------------------------------------------------

class TestKeyLevel:
    def test_kl_type_present(self, bull_entry):
        """Key level type value (e.g. 'FVG') appears."""
        assert "FVG" in format_alert(bull_entry)

    def test_kl_granularity_present(self, bull_entry):
        """Key level granularity ('D') appears."""
        result = format_alert(bull_entry)
        assert "FVG D" in result

    def test_order_block_kl_type(self):
        """'Order Block' appears when key_level type is ORDER_BLOCK."""
        entry = _make_entry(kl_type=KeyLevelType.ORDER_BLOCK)
        assert "Order Block" in format_alert(entry)

    def test_no_key_level_renders_gracefully(self, score_b_entry):
        """Score B entry with key_level=None renders '—' and does not raise."""
        result = format_alert(score_b_entry)
        assert isinstance(result, str)
        assert "—" in result


# ---------------------------------------------------------------------------
# Timestamp
# ---------------------------------------------------------------------------

class TestTimestamp:
    def test_date_present(self, bull_entry):
        """Year/month/day appears in message."""
        assert "2026-03-27" in format_alert(bull_entry)

    def test_time_present(self, bull_entry):
        """Hour:minute appears in message."""
        assert "17:45" in format_alert(bull_entry)

    def test_utc_label_present(self, bull_entry):
        """'UTC' label appears in message."""
        assert "UTC" in format_alert(bull_entry)


# ---------------------------------------------------------------------------
# Return type
# ---------------------------------------------------------------------------

class TestReturnType:
    def test_returns_str(self, bull_entry):
        assert isinstance(format_alert(bull_entry), str)

    def test_non_empty(self, bull_entry):
        assert len(format_alert(bull_entry)) > 0
