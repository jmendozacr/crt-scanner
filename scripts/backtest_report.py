from __future__ import annotations

import csv
import dataclasses
from pathlib import Path

from scripts.backtest_engine import FunnelCounts, TradeRecord


@dataclasses.dataclass
class BacktestStats:
    total: int
    wins: int
    win_rate: float
    mean_rr: float
    by_session: dict[str, "BacktestStats"] = dataclasses.field(default_factory=dict)
    by_pair: dict[str, "BacktestStats"] = dataclasses.field(default_factory=dict)


def _leaf_stats(trades: list[TradeRecord]) -> BacktestStats:
    total = len(trades)
    wins = sum(1 for t in trades if t.result == "WIN")
    win_rate = round(wins / total * 100, 2) if total > 0 else 0.0
    win_trades = [t for t in trades if t.result == "WIN"]
    mean_rr = (
        round(sum(t.rr for t in win_trades) / len(win_trades), 2) if win_trades else 0.0
    )
    return BacktestStats(total=total, wins=wins, win_rate=win_rate, mean_rr=mean_rr)


def aggregate(trades: list[TradeRecord]) -> BacktestStats:
    stats = _leaf_stats(trades)
    sessions: dict[str, list[TradeRecord]] = {}
    pairs: dict[str, list[TradeRecord]] = {}
    for t in trades:
        sessions.setdefault(t.session, []).append(t)
        pairs.setdefault(t.symbol, []).append(t)
    stats.by_session = {s: _leaf_stats(ts) for s, ts in sessions.items()}
    stats.by_pair = {p: _leaf_stats(ps) for p, ps in pairs.items()}
    return stats


def print_report(
    trades: list[TradeRecord],
    stats: BacktestStats,
    funnels: list[FunnelCounts],
) -> None:
    SEP = "=" * 70
    print(SEP)
    print("BACKTEST MODE — CRT Strategy Walk-Forward Report")
    print(
        "Note: CRT detection limited to 1day timeframe (live scanner uses 1day+2day+3day)"
    )
    print(SEP)

    # Trade ledger
    if trades:
        print(f"\n{'SYMBOL':<12}{'DATE':<22}{'BIAS':<10}{'RESULT':<8}{'RR':<6}BARS_TO_TP")
        print("-" * 70)
        for t in trades:
            print(
                f"{t.symbol:<12}{t.entry_datetime:<22}{t.bias:<10}{t.result:<8}{t.rr:<6}{t.bars_to_tp}"
            )

    # Funnel per pair
    for f in funnels:
        print(f"\nFunnel ({f.symbol}):")
        print(f"  M15 steps:     {f.total_m15_steps}")
        print(f"  Passed TS:     {f.passed_ts}")
        print(f"  Passed session:{f.passed_session}")
        print(f"  Passed TBS:    {f.passed_tbs}")
        print(f"  Passed Model1: {f.passed_model1}")

    # Summary
    print(f"\n{SEP}")
    print(
        f"SUMMARY: {stats.total} trades, {stats.wins} wins ({stats.win_rate:.2f}%), mean RR {stats.mean_rr:.2f}"
    )

    # By pair
    if stats.by_pair:
        print("\nBy Pair:")
        for sym, s in stats.by_pair.items():
            print(
                f"  {sym:<12}: {s.total} trades, {s.wins} wins ({s.win_rate:.2f}%), mean RR {s.mean_rr:.2f}"
            )

    # By session
    if stats.by_session:
        print("\nBy Session:")
        for sess, s in stats.by_session.items():
            print(
                f"  {sess:<15}: {s.total} trades, {s.wins} wins ({s.win_rate:.2f}%), mean RR {s.mean_rr:.2f}"
            )


def save_csv(trades: list[TradeRecord], path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fields = [f.name for f in dataclasses.fields(TradeRecord)]
    with open(p, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for t in trades:
            writer.writerow(dataclasses.asdict(t))
