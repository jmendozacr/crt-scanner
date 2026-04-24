from dataclasses import dataclass


@dataclass(frozen=True)
class Pair:
    symbol: str
    smt_partner: str
    smt_correlation: str  # "positive" or "negative"


PAIRS: list[Pair] = [
    Pair(symbol="EUR/USD", smt_partner="GBP/USD", smt_correlation="positive"),
    Pair(symbol="GBP/USD", smt_partner="EUR/USD", smt_correlation="positive"),
    Pair(symbol="USD/CAD", smt_partner="EUR/USD", smt_correlation="negative"),
]

SYMBOLS: list[str] = [p.symbol for p in PAIRS]
