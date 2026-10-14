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

from ..types import Day, Dec, UtcTimestamp
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
    # Reading it (S9.8): where it stands, how and with what it was read, the full text (also
    # in ReceiptSearch for search), the suggested fields with their confidences, and which of
    # its fields still hold a suggestion rather than what a person typed.
    Column("readStatus", Text, nullable=False, server_default=text("'waiting'")),
    Column("readError", Text),
    Column("readMethod", Text),
    Column("readEngine", Text),
    Column("readAt", UtcTimestamp),
    Column("text", Text),
    Column("suggested", Text, nullable=False, server_default=text("'{}'")),
    Column("filled", Text, nullable=False, server_default=text("'[]'")),
    CheckConstraint(
        "\"readStatus\" IN ('off', 'waiting', 'reading', 'read', 'failed')", name="read_status"
    ),
    CheckConstraint(
        "\"mediaType\" IN ('application/pdf', 'image/jpeg', 'image/png', 'image/webp', "
        "'image/heic')",
        name="media_type",
    ),
    Index("ix_Receipt_ownerId", "ownerId"),
    Index("ix_Receipt_sha256", "sha256"),
)

# What a receipt is attached to (S9.3): transactions, an account (a statement kept as a
# receipt, S1.3.3), a physical-asset item's photos and documents (S1.10.1), a 529's qualified
# expenses (S1.8.3), gifts (S7.8.1), donations' acknowledgements (S8.9), and other kinds as
# they are built.
ReceiptLinks = pairs(
    "ReceiptLinks",
    Column("receiptId", Text, ForeignKey("Receipt.id", ondelete="CASCADE"), nullable=False),
    Column("kind", Text, nullable=False),
    Column("itemId", Text, nullable=False),
    Column("linkedById", Text, ForeignKey("User.id")),
    PrimaryKeyConstraint("receiptId", "kind", "itemId"),
    CheckConstraint(
        "kind IN ('transaction', 'account', 'item', 'expense', 'gift', 'donation')",
        name="kind",
    ),
    Index("ix_ReceiptLinks_item", "kind", "itemId"),
)

# The full-text index of what was read (SQLite FTS5), kept by the reader, searched by the
# Receipts screen. A virtual table, made by revision 0007 rather than declared here.
SEARCH = "ReceiptSearch"


def is_search_table(name: str) -> bool:
    """FTS5's table and the shadow tables it keeps beside it."""
    return name == SEARCH or name.startswith(SEARCH + "_")
