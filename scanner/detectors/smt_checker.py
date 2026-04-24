from __future__ import annotations

from dataclasses import dataclass

from scanner.data.candle import Candle
from scanner.detectors._common import Bias, exclude_live


@dataclass(frozen=True)
class SMTResult:
    """Result of an SMT divergence check between two correlated instruments."""

    has_divergence: bool
    note: str
    primary_symbol: str
    partner_symbol: str
    correlation: str  # "positive" or "negative"


def check_smt(
    primary_candles: list[Candle],
    partner_candles: list[Candle],
    *,
    bias: Bias,
    primary_symbol: str,
    partner_symbol: str,
    correlation: str,
) -> SMTResult:
    """Check for SMT divergence between primary and partner instruments.

    Always returns an SMTResult — never raises, never returns None.
    """
    primary_closed = exclude_live(primary_candles)
    partner_closed = exclude_live(partner_candles)

    if len(primary_closed) < 2 or len(partner_closed) < 2:
        return SMTResult(
            has_divergence=False,
            note="SMT: insufficient data",
            primary_symbol=primary_symbol,
            partner_symbol=partner_symbol,
            correlation=correlation,
        )

    p_prev, p_curr = primary_closed[-2], primary_closed[-1]
    q_prev, q_curr = partner_closed[-2], partner_closed[-1]

    has_div: bool

    if bias is Bias.BULLISH:
        primary_new_low = p_curr.low < p_prev.low
        if correlation == "positive":
            partner_new_low = q_curr.low < q_prev.low
            has_div = primary_new_low and not partner_new_low
        else:
            # Negative correlation: partner should make a new high if primary makes a new low
            partner_new_high = q_curr.high > q_prev.high
            has_div = primary_new_low and not partner_new_high
    else:
        primary_new_high = p_curr.high > p_prev.high
        if correlation == "positive":
            partner_new_high = q_curr.high > q_prev.high
            has_div = primary_new_high and not partner_new_high
        else:
            # Negative correlation: partner should make a new low if primary makes a new high
            partner_new_low = q_curr.low < q_prev.low
            has_div = primary_new_high and not partner_new_low

    if has_div:
        note = f"SMT divergence: {primary_symbol} vs {partner_symbol} ({correlation})"
    else:
        note = ""

    return SMTResult(
        has_divergence=has_div,
        note=note,
        primary_symbol=primary_symbol,
        partner_symbol=partner_symbol,
        correlation=correlation,
    )
