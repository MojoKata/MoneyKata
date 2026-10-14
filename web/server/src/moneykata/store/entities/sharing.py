import datetime as dt
from dataclasses import dataclass

from . import Record


@dataclass(kw_only=True, eq=False)
class Portfolio(Record):
    id: str
    ownerId: str
    name: str
    benchmark: str = "VT"
    notes: str | None = None


@dataclass(kw_only=True, eq=False)
class PortfolioAccount:
    portfolioId: str
    accountId: str
    createdAt: dt.datetime
    deleted: bool = False
    deletedAt: dt.datetime | None = None
    deletedById: str | None = None


@dataclass(kw_only=True, eq=False)
class Share(Record):
    id: str
    kind: str
    itemId: str
    level: str
    userId: str | None = None
    groupId: str | None = None
    createdById: str | None = None
    includeReceipts: bool = False


@dataclass(kw_only=True, eq=False)
class CountedAccount:
    userId: str
    accountId: str
    createdAt: dt.datetime
    counted: bool = True
    deleted: bool = False
    deletedAt: dt.datetime | None = None
    deletedById: str | None = None
