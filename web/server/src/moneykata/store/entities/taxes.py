import datetime as dt
from dataclasses import dataclass
from decimal import Decimal

from . import Record, SoftDeleted


@dataclass(kw_only=True, eq=False)
class TaxBook(Record):
    id: str
    ownerId: str
    year: int

    @property
    def name(self) -> str:
        """What the Share dialog calls it."""
        return f"Tax book {self.year}"


@dataclass(kw_only=True, eq=False)
class TaxBookFiler(SoftDeleted):
    bookId: str
    userId: str
    createdAt: dt.datetime
    acceptedAt: dt.datetime | None = None
    deletedAt: dt.datetime | None = None
    deletedById: str | None = None


@dataclass(kw_only=True, eq=False)
class TaxBookAccount(SoftDeleted):
    bookId: str
    accountId: str
    counted: bool
    createdAt: dt.datetime
    deletedAt: dt.datetime | None = None
    deletedById: str | None = None


@dataclass(kw_only=True, eq=False)
class Filing(Record):
    id: str
    bookId: str
    jurisdiction: str
    form: str
    place: str | None = None
    amendsId: str | None = None
    filingStatus: str | None = None
    preparedBy: str | None = None
    sentBy: str | None = None
    progress: str = "not started"
    dueDate: dt.date | None = None
    extensionFiledOn: dt.date | None = None
    extendedDue: dt.date | None = None
    filedOn: dt.date | None = None
    confirmation: str | None = None
    resultKind: str | None = None
    resultAmount: Decimal | None = None
    resultTransactionId: str | None = None
    carried: str = "{}"


@dataclass(kw_only=True, eq=False)
class EstimatedPayment(Record):
    id: str
    filingId: str
    quarter: int
    amount: Decimal
    dueDate: dt.date | None = None
    paidOn: dt.date | None = None
    transactionId: str | None = None


@dataclass(kw_only=True, eq=False)
class TaxDocument(Record):
    id: str
    bookId: str
    direction: str
    form: str
    filingId: str | None = None
    issuer: str | None = None
    accountId: str | None = None
    receiptId: str | None = None
    notes: str | None = None
