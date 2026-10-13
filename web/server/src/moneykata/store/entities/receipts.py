import datetime as dt
from dataclasses import dataclass
from decimal import Decimal

from . import Record


@dataclass(kw_only=True, eq=False)
class Receipt(Record):
    id: str
    ownerId: str
    fileName: str
    mediaType: str
    size: int
    sha256: str
    fileId: str
    thumbnail: bytes | None = None
    date: dt.date | None = None
    amount: Decimal | None = None
    payee: str | None = None
    notes: str | None = None
    tags: str = "[]"


@dataclass(kw_only=True, eq=False)
class ReceiptLink:
    receiptId: str
    kind: str
    itemId: str
    createdAt: dt.datetime
    linkedById: str | None = None
    deleted: bool = False
    deletedAt: dt.datetime | None = None
    deletedById: str | None = None
