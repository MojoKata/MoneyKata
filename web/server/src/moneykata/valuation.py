"""What holdings are worth (requirements S4.6, S4.7): every value derived from a price carries
the price's source and `as_of`. Charts and screens read stored prices only, never a price
source during a request.

Prices come, in order, from: the stored daily closes (S4), a value a broker's file reported
for the holding, and the account's last trade in it.
"""

import datetime as dt
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import false, select
from sqlalchemy.orm import Session

from . import clock
from .ledger import balances
from .money import CENT
from .store.entities.accounts import Holding, Instrument, Transaction

ZERO = Decimal(0)


@dataclass(frozen=True)
class Price:
    price: Decimal
    asOf: dt.date
    source: str  # "close" from a price source, "statement", "trade", "fixed"
    stale: bool = False


# Stored closes, installed by prices/refresh.py: the latest on a day, and a range of them.
CloseLookup = Callable[[Session, list[str], dt.date], dict[str, Price]]
CloseHistory = Callable[
    [Session, list[str], dt.date, dt.date], dict[str, list[tuple[dt.date, Decimal]]]
]
_closes: list[CloseLookup] = []
_history: list[CloseHistory] = []


def use_closes(lookup: CloseLookup, history: CloseHistory | None = None) -> None:
    _closes[:] = [lookup]
    _history[:] = [history] if history else []


def prices(s: Session, instrument_ids: list[str], day: dt.date | None = None) -> dict[str, Price]:
    """The latest price on or before the day for each instrument."""
    day = day or clock.today()
    ids_ = list(dict.fromkeys(instrument_ids))
    out: dict[str, Price] = {}
    if not ids_:
        return out
    insts = {i.id: i for i in s.scalars(select(Instrument).where(Instrument.id.in_(ids_)))}
    for iid, inst in insts.items():
        if inst.instrumentClass in ("cash", "money-market"):
            out[iid] = Price(Decimal(1), day, "fixed")
    if _closes:
        for iid, p in _closes[0](s, [i for i in ids_ if i not in out], day).items():
            out[iid] = p
    missing = [i for i in ids_ if i not in out]
    if missing:
        for h in s.scalars(
            select(Holding)
            .where(
                Holding.instrumentId.in_(missing),
                Holding.deleted == false(),
                Holding.asOf <= day,
                Holding.marketValue.is_not(None),
            )
            .order_by(Holding.asOf)
        ):
            if h.quantity:
                out[h.instrumentId] = Price(h.marketValue / h.quantity, h.asOf, "statement")
    missing = [i for i in ids_ if i not in out]
    if missing:
        for txn in s.scalars(
            select(Transaction)
            .where(
                Transaction.instrumentId.in_(missing),
                Transaction.deleted == false(),
                Transaction.price.is_not(None),
                Transaction.date <= day,
            )
            .order_by(Transaction.date)
        ):
            out[txn.instrumentId] = Price(txn.price, txn.date, "trade")
    return out


@dataclass
class Position:
    instrumentId: str
    quantity: Decimal
    costBasis: Decimal | None
    price: Price | None

    @property
    def value(self) -> Decimal | None:
        return None if self.price is None else (self.quantity * self.price.price).quantize(CENT)

    @property
    def gain(self) -> Decimal | None:
        if self.value is None or self.costBasis is None:
            return None
        return self.value - self.costBasis


def positions(s: Session, ledger, day: dt.date | None = None) -> list[Position]:
    """An investing account's holdings from its replayed lots, valued."""
    replay = ledger.replay()
    by: dict[str, list] = {}
    for lot in replay.open:
        by.setdefault(lot.instrumentId, []).append(lot)
    found = prices(s, list(by), day)
    out = []
    for iid, open_lots in by.items():
        qty = sum((x.quantity for x in open_lots), ZERO)
        basis = (
            None
            if any(x.basis is None for x in open_lots)
            else sum((x.basis for x in open_lots), ZERO)
        )
        out.append(Position(iid, qty, basis, found.get(iid)))
    return out


def account_value(s: Session, ledger, investing: bool, day: dt.date | None = None) -> Decimal:
    """Cash plus what the holdings are worth (a holding with no price counts nothing). A
    loan counts what is owed on it, from its terms and payments (S1.9)."""
    from . import loans

    if loans.is_loan(ledger.account.type):
        return loans.value(s, ledger.account, day)
    cash = ledger.balance(day)
    if not investing:
        return cash
    return cash + sum((p.value or ZERO for p in positions(s, ledger, day)), ZERO)


def price_points(
    s: Session, instrument_ids: list[str], first: dt.date, last: dt.date
) -> dict[str, list[tuple[dt.date, Decimal]]]:
    """Every known price of each instrument up to last, oldest first, from the same sources
    as `prices` and in the same precedence: an instrument with stored closes is valued from
    them alone; one without, from statement values and trades."""
    out: dict[str, list[tuple[dt.date, Decimal]]] = {i: [] for i in instrument_ids}
    if not instrument_ids:
        return out
    closed: set[str] = set()
    for iid, p in prices(s, instrument_ids, first).items():
        out[iid].append((p.asOf, p.price))
        if p.source in ("close", "manual", "fixed"):
            closed.add(iid)
    if _history:
        for iid, rows in _history[0](s, instrument_ids, first, last).items():
            out[iid] += rows
            closed.add(iid)
    others = [i for i in instrument_ids if i not in closed]
    if others:
        for h in s.scalars(
            select(Holding).where(
                Holding.instrumentId.in_(others),
                Holding.deleted == false(),
                Holding.asOf > first,
                Holding.asOf <= last,
                Holding.marketValue.is_not(None),
            )
        ):
            if h.quantity:
                out[h.instrumentId].append((h.asOf, h.marketValue / h.quantity))
        statement = {iid for iid in others if out[iid]}
        for t in s.scalars(
            select(Transaction).where(
                Transaction.instrumentId.in_(others),
                Transaction.deleted == false(),
                Transaction.price.is_not(None),
                Transaction.date > first,
                Transaction.date <= last,
            )
        ):
            if t.instrumentId not in statement:
                out[t.instrumentId].append((t.date, t.price))
    for iid in out:
        out[iid] = sorted(dict(out[iid]).items())
    return out


def series(
    s: Session, ledger, investing: bool, first: dt.date, last: dt.date, step_days: int = 1
) -> list[tuple[dt.date, Decimal]]:
    """The account's value at the end of each day (or every step_days), for its chart.
    Positions change only on the days of trades and snapshots, so the ledger is replayed on
    those days alone; prices are carried forward from the last known one."""
    from . import loans

    if loans.is_loan(ledger.account.type):
        row = loans.loan_of(s, ledger.account)
        if row is None:
            return []
        terms = loans.terms_of(row)
        payments, draws = loans.history(s, ledger.account)
        out, day = [], first
        while day <= last:
            out.append((day, -loans.balance_on(terms, payments, draws, day)))
            day += dt.timedelta(days=step_days)
        if out and out[-1][0] != last:
            out.append((last, -loans.balance_on(terms, payments, draws, last)))
        return out
    cash = dict(balances.daily(ledger.opening(), ledger.transactions, first, last))
    days = sorted(cash)
    if step_days > 1:
        days = sorted({*days[::step_days], last})
    if not investing:
        return [(d, cash[d]) for d in days]
    changes = sorted(
        {t.date for t in ledger.transactions if t.instrumentId and first < t.date <= last}
        | {h.asOf for h in ledger.snapshots if first < h.asOf <= last}
    )
    held: list[tuple[dt.date, dict[str, Decimal]]] = [(first, _positions_on(ledger, first))]
    for day in changes:
        held.append((day, _positions_on(ledger, day)))
    ids_ = sorted({i for _, pos in held for i in pos})
    points = price_points(s, ids_, first, last)
    out = []
    h_i = 0
    cursor = {i: 0 for i in ids_}
    current: dict[str, Decimal | None] = {i: None for i in ids_}
    for day in days:
        while h_i + 1 < len(held) and held[h_i + 1][0] <= day:
            h_i += 1
        for iid in ids_:
            pts = points[iid]
            while cursor[iid] < len(pts) and pts[cursor[iid]][0] <= day:
                current[iid] = pts[cursor[iid]][1]
                cursor[iid] += 1
        value = cash[day]
        for iid, qty in held[h_i][1].items():
            if current.get(iid) is not None:
                value += (qty * current[iid]).quantize(CENT)
        out.append((day, value))
    return out


def _positions_on(ledger, day: dt.date) -> dict[str, Decimal]:
    from .ledger import lots as lot_replay

    txns = [t for t in ledger.transactions if t.date <= day]
    used = {t.id for t in txns}
    return lot_replay.replay(
        ledger.account.lotMethod,
        txns,
        [
            x
            for x in ledger.lots
            if x.transactionId in used or (x.transactionId is None and x.acquiredOn <= day)
        ],
        ledger.picks,
        [h for h in ledger.snapshots if h.asOf <= day],
    ).positions()
