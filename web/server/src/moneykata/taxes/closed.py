"""Closed tax years (requirements S2.8): a year is closed for an account once a tax book that
counts the account has its federal return filed or accepted. An edit that would change such a
year's realized gains asks first: the change is worked out, and undone unless confirmed."""

from decimal import Decimal

from sqlalchemy import false, select
from sqlalchemy.orm import Session

from ..errors import Problem
from ..store.entities.accounts import Account
from ..store.entities.taxes import Filing, TaxBook
from ..store.repos import ledger as repo
from . import books

FILED = ("filed", "accepted")


def closed_years(s: Session, account: Account) -> set[int]:
    out: set[int] = set()
    for book in s.scalars(
        select(TaxBook)
        .join(Filing, Filing.bookId == TaxBook.id)
        .where(
            Filing.jurisdiction == "federal",
            Filing.progress.in_(FILED),
            Filing.deleted == false(),
            TaxBook.deleted == false(),
        )
    ):
        if book.year not in out and account.id in {a.id for a in books.counted(s, book).accounts}:
            out.add(book.year)
    return out


def gains(s: Session, account: Account, years: set[int]) -> dict[int, Decimal]:
    out: dict[int, Decimal] = {}
    for d in repo.load(s, account).replay().disposals:
        if d.soldOn.year in years:
            out[d.soldOn.year] = out.get(d.soldOn.year, Decimal(0)) + (d.gain or Decimal(0))
    return out


class Guard:
    """Made before an edit and checked after it: when the edit moved a closed year's gains
    and isn't confirmed, refused with the years named (409 closed-year), so the request's
    unit of work rolls it back."""

    def __init__(self, s: Session, account: Account, confirm: bool):
        self.s, self.account = s, account
        self.years = set() if confirm else closed_years(s, account)
        self.before = gains(s, account, self.years) if self.years else {}

    def check(self) -> None:
        if not self.years:
            return
        self.s.flush()
        after = gains(self.s, self.account, self.years)
        moved = sorted(
            y for y in self.years if self.before.get(y, Decimal(0)) != after.get(y, Decimal(0))
        )
        if moved:
            named = " and ".join(str(y) for y in moved)
            raise Problem(
                409,
                "closed-year",
                f"This changes the realized gains of {named}, a year whose return is filed. "
                "Change it anyway? The return may need amending.",
                extra={"years": moved},
            )
