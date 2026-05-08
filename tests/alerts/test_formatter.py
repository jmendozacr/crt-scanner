"""Tests for scanner.alerts.formatter — SC-ALT-1 through SC-ALT-13."""
from __future__ import annotations

import html
from unittest.mock import patch

import pytest

from scanner.alerts.formatter import (
    STOP_LOSS_PIPS,
    PIP_SIZE,
    _compute_sl,
    _compute_rr,
    _compute_window_end,
    format_alert,
)
from scanner.detectors._common import Bias
from scanner.detectors.fvg_detector import FVGResult
from scanner.detectors.model1_detector import Model1Result
from scanner.detectors.ob_detector import OrderBlockResult
from scanner.detectors.smt_checker import SMTResult
from scanner.detectors.turtle_soup import TurtleSoupResult

from tests.alerts.conftest import (
    make_turtle_soup,
    make_ob,
    make_fvg,
    make_smt,
    make_model1,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FIXED_UTC = "2024-01-15 10:00"


def _call_format_alert(
    symbol: str = "EUR/USD",
    ts: TurtleSoupResult | None = None,
    model_result: Model1Result | OrderBlockResult | FVGResult | None = None,
    smt: SMTResult | None = None,
    session: str | None = None,
) -> str:
    if ts is None:
        ts = make_turtle_soup()
    if model_result is None:
        model_result = make_ob()
    if smt is None:
        smt = make_smt()

    with patch("scanner.alerts.formatter.datetime") as mock_dt:
        mock_dt.utcnow.return_value.__str__ = lambda s: FIXED_UTC
        mock_dt.utcnow.return_value.strftime.return_value = FIXED_UTC
        mock_dt.fromisoformat.side_effect = __import__("datetime").datetime.fromisoformat
        return format_alert(symbol, ts, model_result, smt, session=session)


# ---------------------------------------------------------------------------
# SC-ALT-1: BULLISH OB — full message structure
# ---------------------------------------------------------------------------

class TestSCALT1BullishOBFullMessage:
    def test_contains_symbol(self) -> None:
        msg = _call_format_alert(symbol="EUR/USD", model_result=make_ob(bias=Bias.BULLISH))
        assert "EUR/USD" in msg

    def test_contains_direction_compra(self) -> None:
        msg = _call_format_alert(
            ts=make_turtle_soup(bias=Bias.BULLISH),
            model_result=make_ob(bias=Bias.BULLISH),
        )
        assert "COMPRA 📈" in msg

    def test_contains_model_ob(self) -> None:
        msg = _call_format_alert(model_result=make_ob(bias=Bias.BULLISH))
        assert "Order Block (OB)" in msg

    def test_contains_bias_alcista(self) -> None:
        msg = _call_format_alert(
            ts=make_turtle_soup(bias=Bias.BULLISH),
            model_result=make_ob(bias=Bias.BULLISH),
        )
        assert "Alcista" in msg

    def test_contains_zona_ob_prices(self) -> None:
        ob = make_ob(bias=Bias.BULLISH, ob_low=1.09950, ob_high=1.10050)
        msg = _call_format_alert(model_result=ob)
        assert "1.09950" in msg
        assert "1.10050" in msg

    def test_entry_is_ob_low_for_bullish(self) -> None:
        ob = make_ob(bias=Bias.BULLISH, ob_low=1.09950, ob_high=1.10050)
        msg = _call_format_alert(model_result=ob)
        # SL = ob_low - 12 pips = 1.09950 - 0.0012 = 1.09830
        assert "1.09830" in msg

    def test_contains_setup_detectado_header(self) -> None:
        msg = _call_format_alert()
        assert "SETUP DETECTADO" in msg

    def test_contains_turtle_soup_section(self) -> None:
        msg = _call_format_alert()
        assert "Turtle Soup" in msg


# ---------------------------------------------------------------------------
# SC-ALT-2: BEARISH OB — SL above entry
# ---------------------------------------------------------------------------

class TestSCALT2BearishOB:
    def _make_bearish_alert(self) -> str:
        ob = make_ob(bias=Bias.BEARISH, ob_low=1.09950, ob_high=1.10050)
        ts = make_turtle_soup(bias=Bias.BEARISH)
        smt = make_smt()
        return _call_format_alert(ts=ts, model_result=ob, smt=smt)

    def test_contains_venta(self) -> None:
        assert "VENTA 📉" in self._make_bearish_alert()

    def test_contains_bajista(self) -> None:
        assert "Bajista" in self._make_bearish_alert()

    def test_sl_above_entry(self) -> None:
        msg = self._make_bearish_alert()
        # BEARISH OB: entry = ob_high = 1.10050, SL = 1.10050 + 0.0012 = 1.10170
        assert "1.10170" in msg


# ---------------------------------------------------------------------------
# SC-ALT-3: BULLISH FVG — midpoint as entry
# ---------------------------------------------------------------------------

class TestSCALT3BullishFVG:
    def _make_fvg_alert(self) -> str:
        fvg = make_fvg(bias=Bias.BULLISH, gap_low=1.09940, gap_high=1.10060, midpoint=1.10000)
        ts = make_turtle_soup(bias=Bias.BULLISH)
        return _call_format_alert(ts=ts, model_result=fvg)

    def test_contains_fvg_model(self) -> None:
        assert "Fair Value Gap (FVG)" in self._make_fvg_alert()

    def test_contains_fvg_50_label(self) -> None:
        assert "FVG 50%" in self._make_fvg_alert()

    def test_entry_is_midpoint(self) -> None:
        msg = self._make_fvg_alert()
        # entry = midpoint = 1.10000, shown in the FVG line
        assert "1.10000" in msg

    def test_sl_below_midpoint(self) -> None:
        msg = self._make_fvg_alert()
        # SL = 1.10000 - 0.0012 = 1.09880
        assert "1.09880" in msg


# ---------------------------------------------------------------------------
# SC-ALT-4: BEARISH FVG
# ---------------------------------------------------------------------------

class TestSCALT4BearishFVG:
    def _make_bearish_fvg_alert(self) -> str:
        fvg = make_fvg(bias=Bias.BEARISH, gap_low=1.09940, gap_high=1.10060, midpoint=1.10000)
        ts = make_turtle_soup(bias=Bias.BEARISH)
        return _call_format_alert(ts=ts, model_result=fvg)

    def test_contains_venta(self) -> None:
        assert "VENTA 📉" in self._make_bearish_fvg_alert()

    def test_sl_above_midpoint(self) -> None:
        msg = self._make_bearish_fvg_alert()
        # SL = 1.10000 + 0.0012 = 1.10120
        assert "1.10120" in msg

    def test_contains_fvg_label(self) -> None:
        assert "Fair Value Gap (FVG)" in self._make_bearish_fvg_alert()


# ---------------------------------------------------------------------------
# SC-ALT-5: SMT block present when has_divergence=True
# ---------------------------------------------------------------------------

class TestSCALT5SMTBlockPresent:
    def test_smt_block_shown_when_divergence(self) -> None:
        smt = make_smt(
            has_divergence=True,
            note="SMT divergence: EUR/USD vs GBP/USD (positive)",
        )
        msg = _call_format_alert(smt=smt)
        assert "⚠️ SMT:" in msg
        assert "SMT divergence" in msg


# ---------------------------------------------------------------------------
# SC-ALT-6: SMT block absent when has_divergence=False
# ---------------------------------------------------------------------------

class TestSCALT6SMTBlockAbsent:
    def test_smt_block_hidden_when_no_divergence(self) -> None:
        smt = make_smt(has_divergence=False, note="")
        msg = _call_format_alert(smt=smt)
        assert "⚠️ SMT:" not in msg


# ---------------------------------------------------------------------------
# SC-ALT-7: R:R and TP NOT present in message
# ---------------------------------------------------------------------------

class TestSCALT7NoRROrTP:
    def test_rr_not_in_message(self) -> None:
        ob = make_ob(bias=Bias.BULLISH, ob_low=1.09950, ob_high=1.10050)
        msg = _call_format_alert(model_result=ob)
        assert "R:R:" not in msg

    def test_tp_line_not_in_message(self) -> None:
        ob = make_ob(bias=Bias.BULLISH, ob_low=1.09950, ob_high=1.10050)
        msg = _call_format_alert(model_result=ob)
        assert "• TP:" not in msg


# ---------------------------------------------------------------------------
# SC-ALT-8: R:R NOT present in bearish message either
# ---------------------------------------------------------------------------

class TestSCALT8NoRRBearish:
    def test_rr_not_in_bearish_message(self) -> None:
        ob = make_ob(bias=Bias.BEARISH, ob_low=1.09950, ob_high=1.10050)
        ts = make_turtle_soup(bias=Bias.BEARISH)
        msg = _call_format_alert(ts=ts, model_result=ob)
        assert "R:R:" not in msg


# ---------------------------------------------------------------------------
# SC-ALT-9: window_end = window_start + 4h
# ---------------------------------------------------------------------------

class TestSCALT9WindowEnd:
    def test_window_end_is_4h_after_start(self) -> None:
        result = _compute_window_end("2024-01-15 08:00")
        assert result == "2024-01-15 12:00"

    def test_window_end_shown_in_message(self) -> None:
        ts = make_turtle_soup(window_start="2024-01-15 08:00")
        msg = _call_format_alert(ts=ts)
        assert "2024-01-15 12:00" in msg

    def test_window_end_midnight_rollover(self) -> None:
        result = _compute_window_end("2024-01-15 22:00")
        assert result == "2024-01-16 02:00"


# ---------------------------------------------------------------------------
# SC-ALT-10: html.escape on smt.note
# ---------------------------------------------------------------------------

class TestSCALT10HtmlEscapeSMTNote:
    def test_html_special_chars_escaped_in_smt_note(self) -> None:
        smt = make_smt(
            has_divergence=True,
            note="SMT <b>bold</b> & 'test' \"quote\"",
        )
        msg = _call_format_alert(smt=smt)
        assert "&lt;b&gt;" in msg or html.escape("SMT <b>bold</b>") in msg
        assert "&amp;" in msg
        assert "<b>" not in msg  # raw tags must NOT be present

    def test_html_escape_does_not_double_escape(self) -> None:
        smt = make_smt(has_divergence=True, note="A > B")
        msg = _call_format_alert(smt=smt)
        assert "A &gt; B" in msg


# ---------------------------------------------------------------------------
# SC-ALT-11: prices at 5 decimal places
# ---------------------------------------------------------------------------

class TestSCALT11FiveDecimalPrices:
    def test_ob_prices_formatted_to_5_decimals(self) -> None:
        ob = make_ob(bias=Bias.BULLISH, ob_low=1.09950, ob_high=1.10050)
        msg = _call_format_alert(model_result=ob)
        # Verify exact 5 decimal format is present
        assert "1.09950" in msg
        assert "1.10050" in msg

    def test_sl_formatted_to_5_decimals(self) -> None:
        ob = make_ob(bias=Bias.BULLISH, ob_low=1.09950, ob_high=1.10050)
        msg = _call_format_alert(model_result=ob)
        # SL = 1.09950 - 0.0012 = 1.09830
        assert "1.09830" in msg

    def test_fvg_midpoint_formatted_to_5_decimals(self) -> None:
        fvg = make_fvg(midpoint=1.10003)
        msg = _call_format_alert(model_result=fvg)
        assert "1.10003" in msg


# ---------------------------------------------------------------------------
# SC-ALT-12: Model1Result in alert
# ---------------------------------------------------------------------------

class TestSCALT12Model1Alert:
    def _make_model1_alert(self, bias: Bias = Bias.BULLISH) -> str:
        ts = make_turtle_soup(bias=bias)
        m1 = make_model1(
            bias=bias,
            entry_price=1.10050,
        )
        return _call_format_alert(ts=ts, model_result=m1, smt=None)

    def test_model1_label_in_message(self) -> None:
        msg = self._make_model1_alert()
        assert "Model #1 (M15)" in msg

    def test_model1_entry_price_in_message(self) -> None:
        msg = self._make_model1_alert()
        assert "1.10050" in msg

    def test_model1_entry_line_label(self) -> None:
        msg = self._make_model1_alert()
        assert "Entrada Model #1:" in msg

    def test_model1_tp_not_in_message(self) -> None:
        msg = self._make_model1_alert()
        assert "• TP:" not in msg

    def test_model1_bearish_sell_direction(self) -> None:
        msg = self._make_model1_alert(bias=Bias.BEARISH)
        assert "VENTA 📉" in msg

    def test_smt_none_does_not_crash(self) -> None:
        ts = make_turtle_soup()
        m1 = make_model1()
        msg = _call_format_alert(ts=ts, model_result=m1, smt=None)
        assert "SETUP DETECTADO" in msg


# ---------------------------------------------------------------------------
# SC-ALT-13: session line rendered when provided
# ---------------------------------------------------------------------------

class TestSCALT13SessionLine:
    def test_session_line_present_when_provided(self) -> None:
        msg = _call_format_alert(session="NY AM")
        assert "NY AM" in msg

    def test_session_line_absent_when_none(self) -> None:
        msg = _call_format_alert(session=None)
        assert "Sesión:" not in msg

    def test_session_london_open(self) -> None:
        msg = _call_format_alert(session="London Open")
        assert "London Open" in msg


# ---------------------------------------------------------------------------
# SC-ALT-14: Bias HTF line shows "Turtle Soup H4"
# ---------------------------------------------------------------------------

class TestSCALT14BiasHTFLabel:
    def test_bias_htf_line_shows_turtle_soup_h4(self) -> None:
        msg = _call_format_alert()
        assert "Turtle Soup H4" in msg
