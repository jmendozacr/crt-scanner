"""
Console table report for backtest results.
"""
from __future__ import annotations

from collections import defaultdict

from backtest.evaluator import TradeResult

_COL_WIDTHS = {
    "pair":    10,
    "signals":  8,
    "wins":     6,
    "losses":   7,
    "open":     5,
    "winpct":   8,
    "pf":       6,
}
_SEP = "─" * 57


def _profit_factor(win_pips: list[float], loss_pips: list[float]) -> str:
    gross_win  = sum(win_pips)
    gross_loss = abs(sum(loss_pips))
    if gross_loss == 0:
        return "∞" if gross_win > 0 else "0.0x"
    return f"{gross_win / gross_loss:.1f}x"


def _win_pct(wins: int, losses: int) -> str:
    total = wins + losses
    if total == 0:
        return "—"
    return f"{wins / total * 100:.1f}%"


def _row(
    pair: str,
    signals: int,
    wins: int,
    losses: int,
    opens: int,
    win_pips: list[float],
    loss_pips: list[float],
) -> str:
    pf  = _profit_factor(win_pips, loss_pips)
    pct = _win_pct(wins, losses)
    return (
        f"{pair:<10}{signals:>8}{wins:>6}{losses:>7}{opens:>5}"
        f"  {pct:>7}  {pf:>5}"
    )


def print_report(
    results: list[TradeResult],
    rr: float,
    min_score_label: str,
    lookback: int = 10,
) -> None:
    """Print a grouped console table of backtest results."""
    header = (
        f"Backtest Results  "
        f"(RR 1:{rr:g}, Score {min_score_label}, lookback={lookback}, ~52 days M15)"
    )
    col_header = (
        f"{'Pair':<10}{'Signals':>8}{'Wins':>6}{'Losses':>7}{'Open':>5}"
        f"  {'Win%':>7}  {'PF':>5}"
    )

    print()
    print(header)
    print(_SEP)
    print(col_header)
    print(_SEP)

    if not results:
        print("  No trades found.")
        print(_SEP)
        return

    # Group by pair
    by_pair: dict[str, list[TradeResult]] = defaultdict(list)
    for r in results:
        by_pair[r.pair].append(r)

    all_win_pips: list[float] = []
    all_loss_pips: list[float] = []
    total_wins = total_losses = total_opens = 0

    for pair in sorted(by_pair):
        group = by_pair[pair]
        wins   = [r for r in group if r.outcome == "WIN"]
        losses = [r for r in group if r.outcome == "LOSS"]
        opens  = [r for r in group if r.outcome == "OPEN"]
        wp = [r.pnl_pips for r in wins]
        lp = [r.pnl_pips for r in losses]
        all_win_pips.extend(wp)
        all_loss_pips.extend(lp)
        total_wins    += len(wins)
        total_losses  += len(losses)
        total_opens   += len(opens)
        print(_row(pair, len(group), len(wins), len(losses), len(opens), wp, lp))

    print(_SEP)
    total_signals = len(results)
    print(_row(
        "TOTAL", total_signals,
        total_wins, total_losses, total_opens,
        all_win_pips, all_loss_pips,
    ))
    print(_SEP)
    print()
