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


# ---- across the reader's pipe (S9.8.4.2): to JSON in the worker, checked field by field here

MAX_ROWS = 200_000
TEXT = 500


def to_json(p: ParsedFile) -> dict:
    def row(r: Row) -> dict:
        return {k: _out(v) for k, v in r.__dict__.items()}

    return {
        "format": p.format,
        "rows": [row(r) for r in p.rows],
        "securities": {k: dict(s.__dict__) for k, s in p.securities.items()},
        "positions": [{k: _out(v) for k, v in x.__dict__.items()} for x in p.positions],
        "balances": [[d.isoformat(), str(v)] for d, v in p.balances],
        "coveredFrom": _out(p.coveredFrom),
        "coveredTo": _out(p.coveredTo),
        "institution": p.institution,
        "accountNumber": p.accountNumber,
        "accountKind": p.accountKind,
    }


def _out(v):
    if isinstance(v, dt.date):
        return v.isoformat()
    if isinstance(v, Decimal):
        return str(v)
    return v


class Malformed(ValueError):
    """What the worker answered isn't the shape it must have."""


def _text(v, n: int = TEXT, optional: bool = True) -> str | None:
    if v is None and optional:
        return None
    if not isinstance(v, str) or len(v) > n:
        raise Malformed("a text field")
    return v


def _day(v, optional: bool = True) -> dt.date | None:
    if v is None and optional:
        return None
    try:
        return dt.date.fromisoformat(v)
    except TypeError, ValueError:
        raise Malformed("a date") from None


def _dec(v, optional: bool = True) -> Decimal | None:
    if v is None and optional:
        return None
    if not isinstance(v, str) or len(v) > 40:
        raise Malformed("a number")
    try:
        d = Decimal(v)
    except ArithmeticError:
        raise Malformed("a number") from None
    if not d.is_finite():
        raise Malformed("a number")
    return d


def from_json(d) -> ParsedFile:
    """A parsed file as the worker sent it, each field checked; anything else is refused."""
    if not isinstance(d, dict) or not isinstance(d.get("rows"), list):
        raise Malformed("a parsed file")
    if len(d["rows"]) > MAX_ROWS or d.get("format") not in ("ofx", "csv"):
        raise Malformed("a parsed file")
    rows = []
    for r in d["rows"]:
        if not isinstance(r, dict):
            raise Malformed("a row")
        rows.append(
            Row(
                date=_day(r.get("date"), optional=False),
                kind=_text(r.get("kind"), 30, optional=False),
                amount=_dec(r.get("amount"), optional=False),
                fitId=_text(r.get("fitId")),
                payee=_text(r.get("payee")),
                memo=_text(r.get("memo")),
                security=_text(r.get("security")),
                quantity=_dec(r.get("quantity")),
                price=_dec(r.get("price")),
                fees=_dec(r.get("fees")),
                dividendType=_text(r.get("dividendType"), 30),
                splitRatio=_dec(r.get("splitRatio")),
                runningBalance=_dec(r.get("runningBalance")),
            )
        )
    securities = {}
    raw = d.get("securities") or {}
    if not isinstance(raw, dict) or len(raw) > 10_000:
        raise Malformed("the securities")
    for key, s in raw.items():
        if not isinstance(s, dict):
            raise Malformed("a security")
        securities[_text(key, optional=False)] = Security(
            key=_text(s.get("key"), optional=False),
            symbol=_text(s.get("symbol"), 40),
            name=_text(s.get("name")),
            instrumentClass=_text(s.get("instrumentClass"), 40, optional=False),
            cusip=_text(s.get("cusip"), 20),
        )
    positions = []
    for x in d.get("positions") or []:
        if not isinstance(x, dict):
            raise Malformed("a position")
        positions.append(
            Position(
                security=_text(x.get("security"), optional=False),
                asOf=_day(x.get("asOf"), optional=False),
                quantity=_dec(x.get("quantity"), optional=False),
                marketValue=_dec(x.get("marketValue")),
            )
        )
    balances = []
    for b in d.get("balances") or []:
        if not isinstance(b, list) or len(b) != 2:
            raise Malformed("a balance")
        balances.append((_day(b[0], optional=False), _dec(b[1], optional=False)))
    return ParsedFile(
        format=d["format"],
        rows=rows,
        securities=securities,
        positions=positions,
        balances=balances,
        coveredFrom=_day(d.get("coveredFrom")),
        coveredTo=_day(d.get("coveredTo")),
        institution=_text(d.get("institution")),
        accountNumber=_text(d.get("accountNumber"), 60),
        accountKind=_text(d.get("accountKind"), 20),
    )
