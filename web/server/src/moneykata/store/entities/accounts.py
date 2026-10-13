import datetime as dt
from dataclasses import dataclass
from decimal import Decimal

from . import Record


@dataclass(kw_only=True, eq=False)
class Category(Record):
    id: str
    name: str
    kind: str
    parentId: str | None = None
    taxTag: str | None = None
    builtIn: str | None = None
    createdById: str | None = None


@dataclass(kw_only=True, eq=False)
class Account(Record):
    id: str
    ownerId: str
    name: str
    type: str
    institution: str | None = None
    mask: str | None = None
    active: bool = True
    notes: str | None = None
    keptBy: str = '["manual"]'
    lotMethod: str = "fifo"
    countInNetWorth: bool = True
    openingBalance: Decimal | None = None
    openingDate: dt.date | None = None


@dataclass(kw_only=True, eq=False)
class Instrument(Record):
    id: str
    symbol: str
    instrumentClass: str
    name: str | None = None
    cusip: str | None = None


@dataclass(kw_only=True, eq=False)
class ImportMapping(Record):
    id: str
    ownerId: str
    institution: str
    columns: str


@dataclass(kw_only=True, eq=False)
class StatementLayout(Record):
    id: str
    ownerId: str
    institution: str
    layout: str = "{}"


@dataclass(kw_only=True, eq=False)
class Import(Record):
    id: str
    accountId: str
    userId: str
    format: str
    fileName: str
    fileHash: str
    coveredFrom: dt.date | None = None
    coveredTo: dt.date | None = None
    added: int = 0
    matched: int = 0
    changed: int = 0


@dataclass(kw_only=True, eq=False)
class Transaction(Record):
    id: str
    accountId: str
    date: dt.date
    kind: str
    amount: Decimal
    payee: str | None = None
    payeeRaw: str | None = None
    memo: str | None = None
    categoryId: str | None = None
    instrumentId: str | None = None
    quantity: Decimal | None = None
    price: Decimal | None = None
    fees: Decimal | None = None
    dividendType: str | None = None
    splitRatio: Decimal | None = None
    lotMethod: str | None = None
    contributionYear: int | None = None
    contributionSource: str | None = None
    transferId: str | None = None
    importId: str | None = None
    fitId: str | None = None
    runningBalance: Decimal | None = None
    amountWas: Decimal | None = None
    duplicateAnswer: str | None = None
    cleared: bool = False
    reconciliationId: str | None = None
    createdById: str | None = None


@dataclass(kw_only=True, eq=False)
class Split(Record):
    id: str
    transactionId: str
    amount: Decimal
    categoryId: str | None = None
    memo: str | None = None


@dataclass(kw_only=True, eq=False)
class TransactionTag:
    transactionId: str
    userId: str
    tag: str
    createdAt: dt.datetime
    deleted: bool = False
    deletedAt: dt.datetime | None = None
    deletedById: str | None = None


@dataclass(kw_only=True, eq=False)
class Lot(Record):
    id: str
    accountId: str
    instrumentId: str
    acquiredOn: dt.date
    quantity: Decimal
    transactionId: str | None = None
    costBasis: Decimal | None = None
    basisMissing: bool = False


@dataclass(kw_only=True, eq=False)
class LotPick:
    saleId: str
    lotId: str
    quantity: Decimal
    createdAt: dt.datetime
    deleted: bool = False
    deletedAt: dt.datetime | None = None
    deletedById: str | None = None


@dataclass(kw_only=True, eq=False)
class Holding(Record):
    id: str
    accountId: str
    instrumentId: str
    asOf: dt.date
    quantity: Decimal
    marketValue: Decimal | None = None
    importId: str | None = None


@dataclass(kw_only=True, eq=False)
class Anchor(Record):
    id: str
    accountId: str
    date: dt.date
    balance: Decimal
    source: str
    importId: str | None = None
    note: str | None = None
    createdById: str | None = None


@dataclass(kw_only=True, eq=False)
class Reconciliation(Record):
    id: str
    accountId: str
    statementDate: dt.date
    statementBalance: Decimal
    finishedAt: dt.datetime | None = None
    finishedById: str | None = None
