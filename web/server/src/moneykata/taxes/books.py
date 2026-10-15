"""Tax books (requirements S8.14–S8.17): who holds one (its accepted filers as owners, others
through a share), the accounts it counts, the federal due date, the documents expected from the
accounts held and last year's, and what last year's filings carried forward."""

import datetime as dt
import json
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import false, func, or_, select
from sqlalchemy.orm import Session

from .. import access, clock
from ..projections import taxtables
from ..store.entities.accounts import Account, Transaction
from ..store.entities.taxes import (
    Filing,
    TaxBook,
    TaxBookAccount,
    TaxBookFiler,
    TaxDocument,
)
from ..store.entities.users import User

CARRIED = (
    "agi",
    "totalTax",
    "refund",
    "owed",
    "overpaymentApplied",
    "capitalLossShort",
    "capitalLossLong",
    "basis8606",
    "charitableCarryover",
)


def filers(s: Session, book: TaxBook) -> list[TaxBookFiler]:
    return list(
        s.scalars(
            select(TaxBookFiler)
            .where(TaxBookFiler.bookId == book.id, TaxBookFiler.deleted == false())
            .order_by(TaxBookFiler.createdAt)
        )
    )


def level(s: Session, user_id: str, book: TaxBook, r=None) -> str | None:
    """owner for the one who made it and its accepted filers; else a share's level."""
    if book.deleted:
        return None
    if book.ownerId == user_id:
        return "owner"
    for f in filers(s, book):
        if f.userId == user_id and f.acceptedAt is not None:
            return "owner"
    r = r or access.reach(s, user_id)
    return r.levels.get(("tax-book", book.id))


def visible(s: Session, user_id: str) -> list[tuple[TaxBook, str]]:
    """The books the user holds or helps with, and those they are named in, to accept."""
    r = access.reach(s, user_id)
    shared = [i for (k, i) in r.levels if k == "tax-book"]
    named = select(TaxBookFiler.bookId).where(
        TaxBookFiler.userId == user_id, TaxBookFiler.deleted == false()
    )
    rows = s.scalars(
        select(TaxBook)
        .where(
            TaxBook.deleted == false(),
            or_(TaxBook.ownerId == user_id, TaxBook.id.in_(shared), TaxBook.id.in_(named)),
        )
        .order_by(TaxBook.year.desc(), TaxBook.createdAt)
    ).all()
    out = []
    for b in rows:
        lvl = level(s, user_id, b, r) or "pending"
        out.append((b, lvl))
    return out


def get(s: Session, user_id: str, book_id: str, need: str = "read") -> tuple[TaxBook, str]:
    from ..errors import Problem

    b = s.get(TaxBook, book_id)
    lvl = level(s, user_id, b) if b is not None else None
    if lvl is None:
        raise Problem(404, "not-found", "Not found")
    if access.RANK[lvl] < access.RANK[need]:
        raise Problem(403, "read-only", "This tax book is shared with you to read.")
    return b, lvl


def overrides(s: Session, book: TaxBook) -> dict[str, bool]:
    return {
        o.accountId: o.counted
        for o in s.scalars(
            select(TaxBookAccount).where(
                TaxBookAccount.bookId == book.id, TaxBookAccount.deleted == false()
            )
        )
    }


@dataclass
class Counted:
    accounts: list[Account]  # counted, each once
    leftOut: list[Account]  # the filers' own, left out
    added: list[str]  # ids counted though not the filers' own


def counted(s: Session, book: TaxBook) -> Counted:
    """The accepted filers' own accounts, each once even when they share them with each
    other, plus those added, less those left out (S8.14.2)."""
    who = [f.userId for f in filers(s, book) if f.acceptedAt is not None]
    own = list(
        s.scalars(
            select(Account)
            .where(Account.ownerId.in_(who), Account.deleted == false())
            .order_by(Account.name)
        )
    )
    over = overrides(s, book)
    kept = [a for a in own if over.get(a.id, True)]
    left = [a for a in own if not over.get(a.id, True)]
    added = [i for i, on in over.items() if on and i not in {a.id for a in own}]
    extra = [a for a in (s.get(Account, i) for i in added) if a is not None and not a.deleted]
    return Counted(kept + extra, left, added)


def federal_due(s: Session, year: int) -> dt.date:
    """The federal return's due date for a tax year, from the tax tables (the following
    year's April 15), moved to the next weekday."""
    month, day = taxtables.figures(s, year)["federalDue"]
    due = dt.date(year + 1, int(month), int(day))
    while due.weekday() >= 5:
        due += dt.timedelta(days=1)
    return due


def filings(s: Session, book: TaxBook) -> list[Filing]:
    return list(
        s.scalars(
            select(Filing)
            .where(Filing.bookId == book.id, Filing.deleted == false())
            .order_by(Filing.jurisdiction, Filing.createdAt)
        )
    )


def due_of(f: Filing) -> dt.date | None:
    return f.extendedDue or f.dueDate


def overdue(f: Filing, today: dt.date) -> bool:
    """Past its due date, not filed, and no extension that still runs (S8.15)."""
    due = due_of(f)
    return (
        due is not None
        and due < today
        and f.progress not in ("filed", "accepted")
        and f.amendsId is None
    )


def documents(s: Session, book: TaxBook) -> list[TaxDocument]:
    return list(
        s.scalars(
            select(TaxDocument)
            .where(TaxDocument.bookId == book.id, TaxDocument.deleted == false())
            .order_by(TaxDocument.createdAt)
        )
    )


@dataclass
class Expected:
    form: str
    issuer: str | None
    accountId: str | None
    why: str  # what makes it expected
    document: TaxDocument | None = None  # received, when it is


def _moved(s: Session, a: Account, year: int, out: bool) -> bool:
    """Whether money left (or came into) the account in the year, beyond trades."""
    q = (
        select(func.count())
        .select_from(Transaction)
        .where(
            Transaction.accountId == a.id,
            Transaction.deleted == false(),
            Transaction.date >= dt.date(year, 1, 1),
            Transaction.date <= dt.date(year, 12, 31),
            Transaction.instrumentId.is_(None),
            Transaction.amount < 0 if out else Transaction.amount > 0,
        )
    )
    return bool(s.scalar(q))


def _interest(s: Session, a: Account, year: int) -> Decimal:
    return s.scalar(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            Transaction.accountId == a.id,
            Transaction.deleted == false(),
            Transaction.kind == "interest",
            Transaction.date >= dt.date(year, 1, 1),
            Transaction.date <= dt.date(year, 12, 31),
        )
    ) or Decimal(0)


def expected(s: Session, book: TaxBook) -> list[Expected]:
    """The documents expected (S8.8, S8.16.1): from each counted account, and every one
    received last year; each matched to what was received."""
    y = book.year
    out: list[Expected] = []
    for a in counted(s, book).accounts:
        inst = a.institution or a.name
        forms: list[tuple[str, str]] = []
        if a.type == "brokerage":
            forms.append(("1099 (composite)", "a taxable brokerage account"))
        elif a.type in ("checking", "savings", "money-market", "cd"):
            if _interest(s, a, y) >= 10:
                forms.append(("1099-INT", "$10 or more of interest"))
        elif a.type in ("ira", "roth-ira"):
            if _moved(s, a, y, out=False):
                forms.append(("5498", "contributions"))
            if _moved(s, a, y, out=True):
                forms.append(("1099-R", "distributions"))
        elif a.type in ("401k", "403b", "457b"):
            if _moved(s, a, y, out=True):
                forms.append(("1099-R", "distributions"))
        elif a.type == "hsa":
            forms.append(("5498-SA", "an HSA"))
            if _moved(s, a, y, out=True):
                forms.append(("1099-SA", "distributions"))
        elif a.type == "529":
            if _moved(s, a, y, out=True):
                forms.append(("1099-Q", "withdrawals"))
        elif a.type in ("mortgage", "heloc"):
            forms.append(("1098", "mortgage interest"))
        elif a.type == "student-loan":
            forms.append(("1098-E", "student-loan interest"))
        elif a.type == "crypto-exchange":
            forms.append(("1099-DA", "a crypto exchange"))
        for form, why in forms:
            out.append(Expected(form, inst, a.id, f"From {a.name}: {why}"))
    # Last year's received documents are expected again (S8.14.4).
    prev = previous(s, book)
    if prev is not None:
        for d in documents(s, prev):
            if d.direction != "received":
                continue
            if any(
                e.form == d.form
                and (
                    (e.accountId is not None and e.accountId == d.accountId)
                    or (e.issuer is not None and e.issuer == d.issuer)
                )
                for e in out
            ):
                continue
            out.append(Expected(d.form, d.issuer, d.accountId, f"Received in {prev.year}"))
    # A dependent's documents (S8.14.5.3): a student's 1098-T, and a childcare provider's
    # statement when childcare was paid for one under 13.
    from . import dependents

    deps = dependents.listed(s, book)
    # Last year's 1098-Ts, expected again from their college, stand for the first students.
    known = sum(e.form == "1098-T" for e in out)
    for d in [d for d in deps if d.row.student][known:]:
        out.append(Expected("1098-T", None, None, f"For {d.person.name}: a student"))
    young = [d.person.name for d in deps if d.under13]
    if young and dependents.childcare_paid(s, book, [a.id for a in counted(s, book).accounts]):
        out.append(
            Expected(
                "Childcare provider statement",
                None,
                None,
                f"For {' and '.join(young)}: childcare paid",
            )
        )
    received = [d for d in documents(s, book) if d.direction == "received"]
    used: set[str] = set()
    for e in out:
        for d in received:
            if d.id in used or d.form != e.form:
                continue
            if (
                (e.accountId and d.accountId == e.accountId)
                or (e.issuer and (d.issuer or "").lower() == e.issuer.lower())
                or (e.accountId is None and e.issuer is None)
            ):
                e.document = d
                used.add(d.id)
                break
    return out


def previous(s: Session, book: TaxBook) -> TaxBook | None:
    """Last year's book of the same filers (or one of them)."""
    mine = {f.userId for f in filers(s, book)}
    for b in s.scalars(
        select(TaxBook)
        .where(TaxBook.year == book.year - 1, TaxBook.deleted == false())
        .order_by(TaxBook.createdAt)
    ):
        if mine & {f.userId for f in filers(s, b)}:
            return b
    return None


def carried_from_last_year(s: Session, book: TaxBook) -> list[tuple[Filing, dict]]:
    prev = previous(s, book)
    if prev is None:
        return []
    out = []
    for f in filings(s, prev):
        figures = json.loads(f.carried or "{}")
        if any(figures.get(k) not in (None, "") for k in CARRIED):
            out.append((f, figures))
    return out


def names(s: Session, ids: list[str]) -> dict[str, str]:
    return {u.id: u.displayName for u in s.scalars(select(User).where(User.id.in_(ids)))}


def today() -> dt.date:
    return clock.today()
