"""What holdings are worth (requirements §7.6, §7.7): every value derived from a price carries
the price's source and `as_of`. Charts and screens read stored prices only, never a price
source during a request.

Prices come, in order, from: the stored daily closes (§7), a value a broker's file reported
for the holding, and the account's last trade in it.
"""

import datetime as dt
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import false, select
from sqlalchemy.orm import Session

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


# A lookup of stored closes: (instrument ids, day) → {id: Price}. Prices (part 6) installs it.
CloseLookup = Callable[[Session, list[str], dt.date], dict[str, Price]]
_closes: list[CloseLookup] = []


def use_closes(lookup: CloseLookup) -> None:
    _closes.clear()
    _closes.append(lookup)


def prices(s: Session, instrument_ids: list[str], day: dt.date | None = None) -> dict[str, Price]:
    """The latest price on or before the day for each instrument."""
    day = day or dt.date.today()
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
    """Cash plus what the holdings are worth (a holding with no price counts nothing)."""
    cash = ledger.balance(day)
    if not investing:
        return cash
    return cash + sum((p.value or ZERO for p in positions(s, ledger, day)), ZERO)


def series(
    s: Session, ledger, investing: bool, first: dt.date, last: dt.date, step_days: int = 1
) -> list[tuple[dt.date, Decimal]]:
    """The account's value at the end of each day (or every step_days), for its chart."""
    cash = dict(balances.daily(ledger.opening(), ledger.transactions, first, last))
    if not investing:
        days = sorted(cash)[::step_days] if step_days > 1 else sorted(cash)
        if days and days[-1] != last:
            days.append(last)
        return [(d, cash[d]) for d in days]
    out = []
    day = first
    while day <= last:
        out.append(
            (day, cash[day] + sum((p.value or ZERO for p in positions(s, ledger, day)), ZERO))
        )
        day += dt.timedelta(days=step_days)
    if out and out[-1][0] != last:
        out.append((last, account_value(s, ledger, True, last)))
    return out
