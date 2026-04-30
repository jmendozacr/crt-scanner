from __future__ import annotations

import csv
from pathlib import Path

import pytest

from scripts.backtest_engine import FunnelCounts, TradeRecord
from scripts.backtest_report import BacktestStats, aggregate, print_report, save_csv


def _make_trades() -> list[TradeRecord]:
    return [
        TradeRecord(
            "EUR/USD", "NY AM", "bullish", 1.1, 1.2, 1.0, "WIN", 2.0, 5,
            "2024-01-02 09:00:00", "2024-01-02 08:45:00",
        ),
        TradeRecord(
            "GBP/USD", "London Open", "bullish", 1.2, 1.4, 1.0, "WIN", 1.5, 3,
            "2024-01-03 03:00:00", "2024-01-03 02:45:00",
        ),
        TradeRecord(
            "EUR/USD", "NY AM", "bearish", 1.3, 1.1, 1.5, "LOSS", 0.0, -1,
            "2024-01-04 10:00:00", "2024-01-04 09:45:00",
        ),
    ]


# ---------------------------------------------------------------------------
# aggregate
# ---------------------------------------------------------------------------


def test_aggregate_totals() -> None:
    stats = aggregate(_make_trades())
    assert stats.total == 3
    assert stats.wins == 2
    assert abs(stats.win_rate - 66.67) < 0.01


def test_aggregate_by_session() -> None:
    stats = aggregate(_make_trades())
    assert "NY AM" in stats.by_session
    assert "London Open" in stats.by_session


def test_aggregate_by_pair() -> None:
    stats = aggregate(_make_trades())
    assert "EUR/USD" in stats.by_pair
    assert "GBP/USD" in stats.by_pair


def test_aggregate_mean_rr_wins_only() -> None:
    """LOSS trade (rr=0.0) must NOT drag down mean_rr."""
    stats = aggregate(_make_trades())
    # wins: rr 2.0 and 1.5 → mean = 1.75
    assert stats.mean_rr == 1.75


def test_aggregate_empty() -> None:
    stats = aggregate([])
    assert stats.total == 0
    assert stats.win_rate == 0.0
    assert stats.mean_rr == 0.0


# ---------------------------------------------------------------------------
# save_csv
# ---------------------------------------------------------------------------


def test_save_csv_writes_all_rows(tmp_path: Path) -> None:
    trades = _make_trades()
    out = tmp_path / "trades.csv"
    save_csv(trades, out)

    assert out.exists()
    with open(out, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 3


def test_save_csv_empty_writes_header_only(tmp_path: Path) -> None:
    out = tmp_path / "empty.csv"
    save_csv([], out)

    assert out.exists()
    with open(out, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        assert reader.fieldnames is not None and len(reader.fieldnames) > 0
    assert len(rows) == 0


# ---------------------------------------------------------------------------
# print_report
# ---------------------------------------------------------------------------


def test_print_report_contains_disclaimer(capsys: pytest.CaptureFixture) -> None:
    trades = _make_trades()
    stats = aggregate(trades)
    funnels = [FunnelCounts(symbol="EUR/USD"), FunnelCounts(symbol="GBP/USD")]
    print_report(trades, stats, funnels)
    captured = capsys.readouterr()
    assert "CRT detection limited to 1day" in captured.out
