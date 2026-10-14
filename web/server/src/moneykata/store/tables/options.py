"""Option contracts (requirements S3.2): what makes an option instrument one: its underlying,
call or put, strike, expiry and the shares a contract covers."""

from sqlalchemy import CheckConstraint, Column, ForeignKey, Index, Integer, Text, text

from ..types import Day, Dec
from ._base import record, unique_live

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
