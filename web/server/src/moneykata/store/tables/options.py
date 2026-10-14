"""Option contracts (requirements S3.2): what makes an option instrument one: its underlying,
call or put, strike, expiry and the shares a contract covers; and wash sales (S3.8)."""

from sqlalchemy import CheckConstraint, Column, ForeignKey, Index, Integer, Text, text

from ..types import Day, Dec, UtcTimestamp
from ._base import exception, record, unique_live

OptionContract = record(
    "OptionContract",
    "OptCt",
    Column("instrumentId", Text, ForeignKey("Instrument.id"), nullable=False),
    Column("underlyingId", Text, ForeignKey("Instrument.id"), nullable=False),
    Column("right", Text, nullable=False),  # call or put
    Column("strike", Dec, nullable=False),
    Column("expiry", Day, nullable=False),
    Column("multiplier", Integer, nullable=False, server_default=text("100")),
    CheckConstraint("\"right\" IN ('call', 'put')", name="right"),
    CheckConstraint("strike > 0", name="strike"),
    CheckConstraint("multiplier > 0", name="multiplier"),
    Index("ix_OptionContract_underlying", "underlyingId", "expiry"),
)
unique_live(OptionContract, "instrumentId")

# A wash sale (S3.8): a loss disallowed because the same instrument was bought within 30 days,
# moved to the replacement's basis with the sold shares' holding period. Worked out from the
# trades whenever they change, and replaced whole: a cache (schema.md §4.4.5).
WashSale = exception(
    "WashSale",
    "cache: worked out again from the transactions whenever they change (§4.4.5)",
    Column("ownerId", Text, ForeignKey("User.id", ondelete="CASCADE"), nullable=False),
    Column("saleId", Text, ForeignKey("Transaction.id", ondelete="CASCADE"), nullable=False),
    Column("replacementId", Text, ForeignKey("Transaction.id", ondelete="CASCADE"), nullable=False),
    Column("quantity", Dec, nullable=False),  # replacement shares used
    Column("disallowed", Dec, nullable=False),
    Column("heldFrom", Day, nullable=False),  # the replacement's holding period starts here
    Column("createdAt", UtcTimestamp, nullable=False),
    prefix="WashS",
)
Index("ix_WashSale_owner", WashSale.c.ownerId)
Index("ix_WashSale_sale", WashSale.c.saleId)
Index("ix_WashSale_replacement", WashSale.c.replacementId)
