from __future__ import annotations

import pytest

from scanner.detectors._common import Bias
from scanner.detectors.crt_bias import CRTResult
from scanner.detectors.fvg_detector import FVGResult
from scanner.detectors.model1_detector import Model1Result
from scanner.detectors.ob_detector import OrderBlockResult
from scanner.detectors.smt_checker import SMTResult
from scanner.detectors.turtle_body_soup import TBSResult
from scanner.detectors.turtle_soup import TurtleSoupResult


def make_crt(
    bias: Bias = Bias.BULLISH,
    timeframe: str = "1day",
    pattern: str = "2-candle",
    tp_level: float = 1.10200,
    sweep_level: float = 1.09800,
    anchor_datetime: str = "2024-01-15 00:00",
) -> CRTResult:
    return CRTResult(
        bias=bias,
        timeframe=timeframe,
        pattern=pattern,
        tp_level=tp_level,
        sweep_level=sweep_level,
        anchor_datetime=anchor_datetime,
    )


def make_turtle_soup(
    bias: Bias = Bias.BULLISH,
    swept_level: float = 1.09800,
    swept_datetime: str = "2024-01-14 08:00",
    ts_candle_datetime: str = "2024-01-15 08:00",
    window_start: str = "2024-01-15 08:00",
    window_end_hint: str = "",
) -> TurtleSoupResult:
    return TurtleSoupResult(
        bias=bias,
        swept_level=swept_level,
        swept_datetime=swept_datetime,
        ts_candle_datetime=ts_candle_datetime,
        window_start=window_start,
        window_end_hint=window_end_hint,
    )


def make_ob(
    bias: Bias = Bias.BULLISH,
    ob_high: float = 1.10050,
    ob_low: float = 1.09950,
    ob_datetime: str = "2024-01-15 09:00",
    confirmation_datetime: str = "2024-01-15 09:15",
) -> OrderBlockResult:
    return OrderBlockResult(
        bias=bias,
        ob_high=ob_high,
        ob_low=ob_low,
        ob_datetime=ob_datetime,
        confirmation_datetime=confirmation_datetime,
    )


def make_fvg(
    bias: Bias = Bias.BULLISH,
    gap_high: float = 1.10060,
    gap_low: float = 1.09940,
    midpoint: float = 1.10000,
    candle_1_datetime: str = "2024-01-15 09:00",
) -> FVGResult:
    return FVGResult(
        bias=bias,
        gap_high=gap_high,
        gap_low=gap_low,
        midpoint=midpoint,
        candle_1_datetime=candle_1_datetime,
    )


def make_smt(
    has_divergence: bool = False,
    note: str = "",
    primary_symbol: str = "EUR/USD",
    partner_symbol: str = "GBP/USD",
    correlation: str = "positive",
) -> SMTResult:
    return SMTResult(
        has_divergence=has_divergence,
        note=note,
        primary_symbol=primary_symbol,
        partner_symbol=partner_symbol,
        correlation=correlation,
    )


def make_tbs(
    bias: Bias = Bias.BULLISH,
    swept_body_level: float = 1.10000,
    swept_swing_datetime: str = "2024-01-15 08:00:00",
    tbs_candle_datetime: str = "2024-01-15 09:15:00",
    window_start: str = "2024-01-15 09:00",
    window_end_hint: str = "",
) -> TBSResult:
    return TBSResult(
        bias=bias,
        swept_body_level=swept_body_level,
        swept_swing_datetime=swept_swing_datetime,
        tbs_candle_datetime=tbs_candle_datetime,
        window_start=window_start,
        window_end_hint=window_end_hint,
    )


def make_model1(
    bias: Bias = Bias.BULLISH,
    model1_candle_datetime: str = "2024-01-15 09:30:00",
    entry_candle_datetime: str = "2024-01-15 09:45:00",
    entry_price: float = 1.10050,
    tp_level: float = 1.10200,
) -> Model1Result:
    return Model1Result(
        bias=bias,
        model1_candle_datetime=model1_candle_datetime,
        entry_candle_datetime=entry_candle_datetime,
        entry_price=entry_price,
        tp_level=tp_level,
    )


@pytest.fixture
def bullish_crt() -> CRTResult:
    return make_crt(bias=Bias.BULLISH)


@pytest.fixture
def bearish_crt() -> CRTResult:
    return make_crt(bias=Bias.BEARISH)


@pytest.fixture
def bullish_ts() -> TurtleSoupResult:
    return make_turtle_soup(bias=Bias.BULLISH)


@pytest.fixture
def bearish_ts() -> TurtleSoupResult:
    return make_turtle_soup(bias=Bias.BEARISH)


@pytest.fixture
def bullish_ob() -> OrderBlockResult:
    return make_ob(bias=Bias.BULLISH)


@pytest.fixture
def bearish_ob() -> OrderBlockResult:
    return make_ob(bias=Bias.BEARISH)


@pytest.fixture
def bullish_fvg() -> FVGResult:
    return make_fvg(bias=Bias.BULLISH)


@pytest.fixture
def bearish_fvg() -> FVGResult:
    return make_fvg(bias=Bias.BEARISH)


@pytest.fixture
def smt_no_divergence() -> SMTResult:
    return make_smt(has_divergence=False, note="")


@pytest.fixture
def smt_with_divergence() -> SMTResult:
    return make_smt(
        has_divergence=True,
        note="SMT divergence: EUR/USD vs GBP/USD (positive)",
    )
