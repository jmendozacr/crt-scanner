from __future__ import annotations

import html
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from scanner.detectors import Bias
from scanner.detectors.fvg_detector import FVGResult
from scanner.detectors.model1_detector import Model1Result
from scanner.detectors.ob_detector import OrderBlockResult

if TYPE_CHECKING:
    from scanner.detectors.crt_bias import CRTResult
    from scanner.detectors.smt_checker import SMTResult
    from scanner.detectors.turtle_soup import TurtleSoupResult

# Task 1.1 — constants live here, NOT in settings (formatter is the sole consumer)
STOP_LOSS_PIPS: int = 12
PIP_SIZE: float = 0.0001


# Task 1.2
def _format_price(price: float) -> str:
    """Format a price to 5 decimal places."""
    return f"{price:.5f}"


# Task 1.3
def _format_direction(bias: Bias) -> str:
    """Return a human-readable direction string with emoji."""
    if bias is Bias.BULLISH:
        return "COMPRA 📈"
    return "VENTA 📉"


# Task 1.4
def _compute_sl(bias: Bias, entry: float) -> float:
    """Compute stop-loss level based on bias and entry price."""
    offset = STOP_LOSS_PIPS * PIP_SIZE
    if bias is Bias.BULLISH:
        return entry - offset
    return entry + offset


# Task 1.5
def _compute_rr(entry: float, sl: float, tp: float) -> float:
    """Compute reward-to-risk ratio. Returns 0.0 when risk is zero."""
    risk = abs(entry - sl)
    if risk == 0.0:
        return 0.0
    reward = abs(tp - entry)
    return reward / risk


# Task 1.6
def _compute_window_end(window_start: str) -> str:
    """Return window_start + 4 hours formatted as 'YYYY-MM-DD HH:MM'."""
    dt = datetime.fromisoformat(window_start)
    end = dt + timedelta(hours=4)
    return end.strftime("%Y-%m-%d %H:%M")


# Tasks 1.7 & 1.8
def _format_model_block(
    model_result: Model1Result | OrderBlockResult | FVGResult,
    bias: Bias,
) -> tuple[str, str, float]:
    """Return (model_name, model_line, entry_price) for Model1, OB, or FVG.

    Model1 entry: entry_price field (open of the counter-directional candle).
    OB entry:
      BULLISH → ob_low  (buy at the bottom of the zone)
      BEARISH → ob_high (sell at the top of the zone)
    FVG entry:
      Both directions → midpoint
    """
    if isinstance(model_result, Model1Result):
        direction = "📈 BUY" if model_result.bias is Bias.BULLISH else "📉 SELL"
        model_name = "Model #1 (M15)"
        model_line = (
            f"Model #1 (M15)\n"
            f"Dirección: {direction}\n"
            f"Entrada Model #1: {_format_price(model_result.entry_price)}\n"
            f"TP: {_format_price(model_result.tp_level)}"
        )
        return model_name, model_line, model_result.entry_price

    if isinstance(model_result, OrderBlockResult):
        model_name = "Order Block (OB)"
        entry = model_result.ob_low if bias is Bias.BULLISH else model_result.ob_high
        model_line = (
            f"Zona OB: {_format_price(model_result.ob_low)} – "
            f"{_format_price(model_result.ob_high)}"
        )
    else:
        model_name = "Fair Value Gap (FVG)"
        entry = model_result.midpoint
        model_line = f"FVG 50%: {_format_price(model_result.midpoint)}"

    return model_name, model_line, entry


# Task 1.9
def format_alert(
    symbol: str,
    crt: CRTResult,
    ts: TurtleSoupResult,
    model_result: Model1Result | OrderBlockResult | FVGResult,
    smt: SMTResult | None,
    session: str | None = None,
) -> str:
    """Assemble the full Telegram HTML alert message."""
    model_name, model_line, entry = _format_model_block(model_result, crt.bias)

    direction = _format_direction(crt.bias)
    bias_label = "Alcista" if crt.bias is Bias.BULLISH else "Bajista"

    sl = _compute_sl(crt.bias, entry)
    tp = crt.tp_level
    rr = _compute_rr(entry, sl, tp)

    window_start = ts.window_start
    window_end = _compute_window_end(window_start)

    current_utc = datetime.utcnow().strftime("%Y-%m-%d %H:%M")

    # Escape all dynamic strings
    safe_symbol = html.escape(symbol)
    safe_direction = html.escape(direction)
    safe_model_name = html.escape(model_name)
    safe_model_line = html.escape(model_line)
    safe_bias_label = html.escape(bias_label)
    safe_timeframe = html.escape(crt.timeframe)
    safe_pattern = html.escape(crt.pattern)
    safe_ts_candle = html.escape(ts.ts_candle_datetime)
    safe_window_start = html.escape(window_start)
    safe_window_end = html.escape(window_end)
    safe_current_utc = html.escape(current_utc)

    smt_block = ""
    if smt is not None and smt.has_divergence:
        smt_block = f"\n⚠️ SMT: {html.escape(smt.note)}\n"

    session_line = ""
    if session is not None:
        session_line = f"\n🕐 Sesión: {html.escape(session)}"

    message = (
        f"🔔 SETUP DETECTADO — {safe_symbol}\n"
        f"\n"
        f"📊 Dirección: {safe_direction}\n"
        f"📐 Modelo: {safe_model_name} (M15)\n"
        f"🏦 Bias HTF: {safe_bias_label} (CRT {safe_timeframe} confirmado, {safe_pattern})\n"
        f"\n"
        f"📍 Entrada:\n"
        f"  • {safe_model_line}\n"
        f"  • SL: {_format_price(sl)} (12 pips)\n"
        f"  • TP: {_format_price(tp)}\n"
        f"  • R:R: 1:{rr:.1f}\n"
        f"\n"
        f"🐢 Turtle Soup:\n"
        f"  • Origen: H4 {safe_ts_candle} UTC\n"
        f"  • Ventana M15: {safe_window_start} – {safe_window_end} UTC"
        f"{smt_block}"
        f"{session_line}\n"
        f"🕐 {safe_current_utc} UTC"
    )

    return message
