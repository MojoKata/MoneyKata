"""Cash balances (requirements R3.2): an opening balance plus the transactions. The opening
balance is typed, or, where none was typed, worked out from the earliest balance the
institution reported, and then marked as standing in for history."""

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal

ZERO = Decimal(0)


@dataclass(frozen=True)
class Opening:
    balance: Decimal
    date: dt.date | None
    standIn: bool  # worked out from a reported balance, not typed


def points(anchors: list, transactions: list) -> list[tuple[dt.date, Decimal, str, str | None]]:
    """Every reported balance, oldest first: anchors, and each day's last running balance from
    a CSV (every row is an anchor, S1.11.2). (date, balance, source, anchor or txn id)."""
    # A statement's ending value is cash and holdings together: checked apart (S1.3.3.8.1).
    out = [(a.date, a.balance, a.source, a.id) for a in anchors if a.source != "statement-value"]
    by_day: dict[dt.date, tuple] = {}
    for t in sorted(transactions, key=lambda t: (t.date, t.createdAt, t.id)):
        if t.runningBalance is not None:
            by_day[t.date] = (t.date, t.runningBalance, "running-balance", t.id)
    out += list(by_day.values())
    return sorted(out, key=lambda p: p[0])


def opening(account, transactions: list, anchors: list) -> Opening:
    if account.openingBalance is not None:
        return Opening(account.openingBalance, account.openingDate, False)
    reported = points(anchors, transactions)
    if not reported:
        return Opening(ZERO, None, False)
    day, balance, _, _ = reported[0]
    before = sum((t.amount for t in transactions if t.date <= day), ZERO)
    first = min((t.date for t in transactions), default=day)
    return Opening(balance - before, first, True)


def balance_on(day: dt.date, start: Opening, transactions: list) -> Decimal:
    return start.balance + sum((t.amount for t in transactions if t.date <= day), ZERO)


def daily(
    start: Opening, transactions: list, first: dt.date, last: dt.date
) -> list[tuple[dt.date, Decimal]]:
    """The end-of-day balance for every day from first to last. Before the account's history
    begins (its opening date, or its first transaction) there is nothing to count: zero."""
    by_day: dict[dt.date, Decimal] = {}
    for t in transactions:
        by_day[t.date] = by_day.get(t.date, ZERO) + t.amount
    begins = start.date or min(by_day, default=None)
    running = start.balance + sum((v for d, v in by_day.items() if d < first), ZERO)
    out = []
    day = first
    while day <= last:
        running += by_day.get(day, ZERO)
        out.append((day, running if begins is None or day >= begins else ZERO))
        day += dt.timedelta(days=1)
    return out
