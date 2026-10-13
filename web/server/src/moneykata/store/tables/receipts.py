"""Receipts (requirements S9): each file encrypted on disk, written once; the database holds
what is known about it, its thumbnail, and what it is attached to."""

from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    PrimaryKeyConstraint,
    Text,
    text,
)

from ..types import Day, Dec
from ._base import pairs, record

Receipt = record(
    "Receipt",
    "Rcpt",
    Column("ownerId", Text, ForeignKey("User.id"), nullable=False),
    Column("fileName", Text, nullable=False),
    Column("mediaType", Text, nullable=False),
    Column("size", Integer, nullable=False),
    # The plaintext's SHA-256: identical files are stored once, found by it, never by name.
    Column("sha256", Text, nullable=False),
    # receipts/<fileId>.mkr: shared by every receipt with the same hash.
    Column("fileId", Text, nullable=False),
    Column("thumbnail", LargeBinary),
    Column("date", Day),
    Column("amount", Dec),
    Column("payee", Text),
    Column("notes", Text),
    Column("tags", Text, nullable=False, server_default=text("'[]'")),
    CheckConstraint(
        "\"mediaType\" IN ('application/pdf', 'image/jpeg', 'image/png', 'image/webp', "
        "'image/heic')",
        name="media_type",
    ),
    Index("ix_Receipt_ownerId", "ownerId"),
    Index("ix_Receipt_sha256", "sha256"),
)

# What a receipt is attached to (S9.3): transactions now, other kinds as they are built.
ReceiptLinks = pairs(
    "ReceiptLinks",
    Column("receiptId", Text, ForeignKey("Receipt.id", ondelete="CASCADE"), nullable=False),
    Column("kind", Text, nullable=False),
    Column("itemId", Text, nullable=False),
    Column("linkedById", Text, ForeignKey("User.id")),
    PrimaryKeyConstraint("receiptId", "kind", "itemId"),
    CheckConstraint("kind IN ('transaction')", name="kind"),
    Index("ix_ReceiptLinks_item", "kind", "itemId"),
)
