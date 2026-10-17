import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal

from . import Record, SoftDeleted, _now


@dataclass(kw_only=True, eq=False)
class PriceSource(Record):
    id: str
    name: str
    enabled: bool = False
    preference: str = "{}"
    lastRunAt: dt.datetime | None = None
    lastOkAt: dt.datetime | None = None
    lastError: str | None = None
    createdById: str | None = None


@dataclass(kw_only=True, eq=False)
class Price(SoftDeleted):
    instrumentId: str
    date: dt.date
    close: Decimal
    source: str
    fetchedAt: dt.datetime = field(default_factory=_now)
    enteredById: str | None = None
    version: int = 1
    updatedAt: dt.datetime = field(default_factory=_now)
    deletedAt: dt.datetime | None = None
    deletedById: str | None = None


@dataclass(kw_only=True, eq=False)
class TypedPrice(SoftDeleted):
    instrumentId: str
    userId: str
    date: dt.date
    close: Decimal
    version: int = 1
    updatedAt: dt.datetime = field(default_factory=_now)
    deletedAt: dt.datetime | None = None
    deletedById: str | None = None
