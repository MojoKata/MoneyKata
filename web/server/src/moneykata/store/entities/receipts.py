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
    readStatus: str = "waiting"
    readError: str | None = None
    readMethod: str | None = None
    readEngine: str | None = None
    readAt: dt.datetime | None = None
    text: str | None = None
    suggested: str = "{}"
    filled: str = "[]"


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
