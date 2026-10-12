"""What a reader finds in a file, before anything is saved."""

import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal


class ReadError(ValueError):
    """The file can't be read; the message is safe to show (no amounts or names)."""


@dataclass
class Security:
    key: str  # how the file names it: a CUSIP, or the ticker
    symbol: str | None
    name: str | None
    instrumentClass: str
    cusip: str | None = None


@dataclass
class Row:
    date: dt.date
    kind: str
    amount: Decimal
    fitId: str | None = None
    payee: str | None = None
    memo: str | None = None
    security: str | None = None  # a Security.key
    quantity: Decimal | None = None
    price: Decimal | None = None
    fees: Decimal | None = None
    dividendType: str | None = None
    splitRatio: Decimal | None = None
    runningBalance: Decimal | None = None


@dataclass
class Position:
    security: str
    asOf: dt.date
    quantity: Decimal
    marketValue: Decimal | None = None


@dataclass
class ParsedFile:
    format: str
    rows: list[Row] = field(default_factory=list)
    securities: dict[str, Security] = field(default_factory=dict)
    positions: list[Position] = field(default_factory=list)
    balances: list[tuple[dt.date, Decimal]] = field(default_factory=list)
    coveredFrom: dt.date | None = None
    coveredTo: dt.date | None = None
    institution: str | None = None
    accountNumber: str | None = None
    accountKind: str | None = None  # bank, card or investment

    def cover(self) -> None:
        """Without dates of its own, a file covers its first to its last row."""
        dates = [r.date for r in self.rows]
        if dates:
            self.coveredFrom = self.coveredFrom or min(dates)
            self.coveredTo = self.coveredTo or max(dates)
