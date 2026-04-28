from dataclasses import dataclass, field


@dataclass(frozen=True)
class Pair:
    symbol: str
    smt_partner: str | None = field(default=None)
    smt_correlation: str | None = field(default=None)  # "positive" or "negative"


PAIRS: list[Pair] = [
    Pair(symbol="EUR/USD", smt_partner="GBP/USD", smt_correlation="positive"),
    Pair(symbol="GBP/USD", smt_partner="EUR/USD", smt_correlation="positive"),
    Pair(symbol="USD/CAD", smt_partner="EUR/USD", smt_correlation="negative"),
    Pair(symbol="BTC/USD"),
]

SYMBOLS: list[str] = [p.symbol for p in PAIRS]
