"""Tests for scanner.detectors.smt_checker — SC-DET-SMT-1 through SC-DET-SMT-8."""
from __future__ import annotations

from scanner.detectors._common import Bias
from scanner.detectors.smt_checker import SMTResult, check_smt

from tests.detectors.conftest import load_fixture, make_candle

PRIMARY = "EUR/USD"
PARTNER_POS = "GBP/USD"
PARTNER_NEG = "USD/CAD"


def _call(
    primary_candles: list,
    partner_candles: list,
    bias: Bias = Bias.BULLISH,
    primary_symbol: str = PRIMARY,
    partner_symbol: str = PARTNER_POS,
    correlation: str = "positive",
) -> SMTResult:
    return check_smt(
        primary_candles,
        partner_candles,
        bias=bias,
        primary_symbol=primary_symbol,
        partner_symbol=partner_symbol,
        correlation=correlation,
    )


# ---------------------------------------------------------------------------
# SC-DET-SMT-1: Positive correlation, primary new low, partner does NOT → divergence
# ---------------------------------------------------------------------------


class TestSCDETSMT1PositiveCorrelationDivergence:
    def test_has_divergence_is_true(self) -> None:
        p_prev = make_candle("2024-01-14 00:00:00", open=1.10000, high=1.10200, low=1.09900, close=1.10100)
        p_curr = make_candle("2024-01-15 00:00:00", open=1.09800, high=1.10000, low=1.09700, close=1.09850)
        live_p = make_candle("2024-01-16 00:00:00")
        q_prev = make_candle("2024-01-14 00:00:00", open=1.28000, high=1.28200, low=1.27900, close=1.28100)
        q_curr = make_candle("2024-01-15 00:00:00", open=1.27900, high=1.28100, low=1.27950, close=1.28000)
        live_q = make_candle("2024-01-16 00:00:00")
        result = _call([p_prev, p_curr, live_p], [q_prev, q_curr, live_q])
        assert result.has_divergence is True

    def test_note_contains_both_symbols(self) -> None:
        p_prev = make_candle("2024-01-14 00:00:00", open=1.10000, high=1.10200, low=1.09900, close=1.10100)
        p_curr = make_candle("2024-01-15 00:00:00", open=1.09800, high=1.10000, low=1.09700, close=1.09850)
        live_p = make_candle("2024-01-16 00:00:00")
        q_prev = make_candle("2024-01-14 00:00:00", open=1.28000, high=1.28200, low=1.27900, close=1.28100)
        q_curr = make_candle("2024-01-15 00:00:00", open=1.27900, high=1.28100, low=1.27950, close=1.28000)
        live_q = make_candle("2024-01-16 00:00:00")
        result = _call([p_prev, p_curr, live_p], [q_prev, q_curr, live_q])
        assert PRIMARY in result.note
        assert PARTNER_POS in result.note


# ---------------------------------------------------------------------------
# SC-DET-SMT-2: Positive correlation, both make new low → no divergence
# ---------------------------------------------------------------------------


class TestSCDETSMT2PositiveCorrelationNoDivergence:
    def test_has_divergence_is_false(self) -> None:
        p_prev = make_candle("2024-01-14 00:00:00", open=1.10000, high=1.10200, low=1.09900, close=1.10100)
        p_curr = make_candle("2024-01-15 00:00:00", open=1.09800, high=1.10000, low=1.09700, close=1.09850)
        live_p = make_candle("2024-01-16 00:00:00")
        q_prev = make_candle("2024-01-14 00:00:00", open=1.28000, high=1.28200, low=1.27900, close=1.28100)
        q_curr = make_candle("2024-01-15 00:00:00", open=1.27800, high=1.28000, low=1.27800, close=1.27850)
        live_q = make_candle("2024-01-16 00:00:00")
        result = _call([p_prev, p_curr, live_p], [q_prev, q_curr, live_q])
        assert result.has_divergence is False

    def test_note_is_empty_string(self) -> None:
        p_prev = make_candle("2024-01-14 00:00:00", open=1.10000, high=1.10200, low=1.09900, close=1.10100)
        p_curr = make_candle("2024-01-15 00:00:00", open=1.09800, high=1.10000, low=1.09700, close=1.09850)
        live_p = make_candle("2024-01-16 00:00:00")
        q_prev = make_candle("2024-01-14 00:00:00", open=1.28000, high=1.28200, low=1.27900, close=1.28100)
        q_curr = make_candle("2024-01-15 00:00:00", open=1.27800, high=1.28000, low=1.27800, close=1.27850)
        live_q = make_candle("2024-01-16 00:00:00")
        result = _call([p_prev, p_curr, live_p], [q_prev, q_curr, live_q])
        assert result.note == ""


# ---------------------------------------------------------------------------
# SC-DET-SMT-3: Negative correlation, primary new low, partner no new high → divergence
# ---------------------------------------------------------------------------


class TestSCDETSMT3NegativeCorrelationDivergence:
    def test_has_divergence_is_true(self) -> None:
        p_prev = make_candle("2024-01-14 00:00:00", open=1.10000, high=1.10200, low=1.09900, close=1.10100)
        p_curr = make_candle("2024-01-15 00:00:00", open=1.09800, high=1.10000, low=1.09700, close=1.09850)
        live_p = make_candle("2024-01-16 00:00:00")
        # partner (negative correlation): expected to make new high but doesn't
        q_prev = make_candle("2024-01-14 00:00:00", open=1.36000, high=1.36200, low=1.35900, close=1.36100)
        q_curr = make_candle("2024-01-15 00:00:00", open=1.36100, high=1.36150, low=1.35900, close=1.36050)
        live_q = make_candle("2024-01-16 00:00:00")
        result = _call(
            [p_prev, p_curr, live_p], [q_prev, q_curr, live_q],
            partner_symbol=PARTNER_NEG, correlation="negative",
        )
        assert result.has_divergence is True


# ---------------------------------------------------------------------------
# SC-DET-SMT-4: Negative correlation, primary new low AND partner new high → no divergence
# ---------------------------------------------------------------------------


class TestSCDETSMT4NegativeCorrelationNoDivergence:
    def test_has_divergence_is_false(self) -> None:
        p_prev = make_candle("2024-01-14 00:00:00", open=1.10000, high=1.10200, low=1.09900, close=1.10100)
        p_curr = make_candle("2024-01-15 00:00:00", open=1.09800, high=1.10000, low=1.09700, close=1.09850)
        live_p = make_candle("2024-01-16 00:00:00")
        # partner makes new high as expected for negative correlation
        q_prev = make_candle("2024-01-14 00:00:00", open=1.36000, high=1.36200, low=1.35900, close=1.36100)
        q_curr = make_candle("2024-01-15 00:00:00", open=1.36100, high=1.36400, low=1.36000, close=1.36300)
        live_q = make_candle("2024-01-16 00:00:00")
        result = _call(
            [p_prev, p_curr, live_p], [q_prev, q_curr, live_q],
            partner_symbol=PARTNER_NEG, correlation="negative",
        )
        assert result.has_divergence is False


# ---------------------------------------------------------------------------
# SC-DET-SMT-5: Primary with fewer than 2 closed candles → has_divergence=False
# ---------------------------------------------------------------------------


class TestSCDETSMT5PrimaryInsufficient:
    def test_has_divergence_false_and_insufficient_note(self) -> None:
        live_p = make_candle("2024-01-15 00:00:00")
        q_prev = make_candle("2024-01-14 00:00:00", open=1.28000, high=1.28200, low=1.27900, close=1.28100)
        q_curr = make_candle("2024-01-15 00:00:00", open=1.27900, high=1.28100, low=1.27950, close=1.28000)
        live_q = make_candle("2024-01-16 00:00:00")
        result = _call([live_p], [q_prev, q_curr, live_q])
        assert result.has_divergence is False
        assert result.note == "SMT: insufficient data"


# ---------------------------------------------------------------------------
# SC-DET-SMT-6: Partner with fewer than 2 closed candles → has_divergence=False
# ---------------------------------------------------------------------------


class TestSCDETSMT6PartnerInsufficient:
    def test_has_divergence_false_and_insufficient_note(self) -> None:
        p_prev = make_candle("2024-01-14 00:00:00", open=1.10000, high=1.10200, low=1.09900, close=1.10100)
        p_curr = make_candle("2024-01-15 00:00:00", open=1.09800, high=1.10000, low=1.09700, close=1.09850)
        live_p = make_candle("2024-01-16 00:00:00")
        live_q = make_candle("2024-01-15 00:00:00")
        result = _call([p_prev, p_curr, live_p], [live_q])
        assert result.has_divergence is False
        assert result.note == "SMT: insufficient data"


# ---------------------------------------------------------------------------
# SC-DET-SMT-7: note is non-empty with divergence; empty string without
# ---------------------------------------------------------------------------


class TestSCDETSMT7NoteContent:
    def test_note_non_empty_when_divergence(self) -> None:
        p_prev = make_candle("2024-01-14 00:00:00", open=1.10000, high=1.10200, low=1.09900, close=1.10100)
        p_curr = make_candle("2024-01-15 00:00:00", open=1.09800, high=1.10000, low=1.09700, close=1.09850)
        live_p = make_candle("2024-01-16 00:00:00")
        q_prev = make_candle("2024-01-14 00:00:00", open=1.28000, high=1.28200, low=1.27900, close=1.28100)
        q_curr = make_candle("2024-01-15 00:00:00", open=1.27900, high=1.28100, low=1.27950, close=1.28000)
        live_q = make_candle("2024-01-16 00:00:00")
        result = _call([p_prev, p_curr, live_p], [q_prev, q_curr, live_q])
        assert result.note != ""

    def test_note_is_empty_string_when_no_divergence(self) -> None:
        p_prev = make_candle("2024-01-14 00:00:00", open=1.10000, high=1.10200, low=1.09900, close=1.10100)
        p_curr = make_candle("2024-01-15 00:00:00", open=1.09800, high=1.10000, low=1.09700, close=1.09850)
        live_p = make_candle("2024-01-16 00:00:00")
        q_prev = make_candle("2024-01-14 00:00:00", open=1.28000, high=1.28200, low=1.27900, close=1.28100)
        q_curr = make_candle("2024-01-15 00:00:00", open=1.27800, high=1.28000, low=1.27800, close=1.27850)
        live_q = make_candle("2024-01-16 00:00:00")
        result = _call([p_prev, p_curr, live_p], [q_prev, q_curr, live_q])
        assert result.note == ""
        assert result.note is not None


# ---------------------------------------------------------------------------
# SC-DET-SMT-8: Smoke test with real EUR/USD (primary) + GBP/USD (partner) H4 fixtures
# ---------------------------------------------------------------------------


class TestSCDETSMT8Smoke:
    def test_smoke_eurusd_gbpusd_h4(self) -> None:
        primary_candles = load_fixture("EUR/USD", "4h")
        partner_candles = load_fixture("GBP/USD", "4h")
        result = check_smt(
            primary_candles,
            partner_candles,
            bias=Bias.BULLISH,
            primary_symbol="EUR/USD",
            partner_symbol="GBP/USD",
            correlation="positive",
        )
        assert isinstance(result, SMTResult)
        assert isinstance(result.has_divergence, bool)
        assert isinstance(result.note, str)
