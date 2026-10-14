"""People (requirements S7.7): someone in a user's life, who need not be a user of the server,
kept on the owner's own list. A 529's beneficiary is one (S1.8.1); Gifts uses them too."""

from sqlalchemy import CheckConstraint, Column, ForeignKey, Index, Integer, Text, text

from ..types import Dec
from ._base import record

Person = record(
    "Person",
    "Persn",
    Column("ownerId", Text, ForeignKey("User.id"), nullable=False),
    Column("name", Text, nullable=False),
    Column("relationship", Text),  # child, parent, sibling, partner, friend, …
    Column("userId", Text, ForeignKey("User.id")),  # when they are a user of this server
    # The birthday: the year is optional, for their age.
    Column("birthMonth", Integer),
    Column("birthDay", Integer),
    Column("birthYear", Integer),
    Column("giftBudget", Dec),  # a year
    Column("leadDays", Integer, nullable=False, server_default=text("14")),
    Column("notes", Text),
    CheckConstraint('"birthMonth" IS NULL OR "birthMonth" BETWEEN 1 AND 12', name="birth_month"),
    CheckConstraint('"birthDay" IS NULL OR "birthDay" BETWEEN 1 AND 31', name="birth_day"),
    CheckConstraint('"leadDays" >= 0', name="lead_days"),
    Index("ix_Person_ownerId", "ownerId"),
)
