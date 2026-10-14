"""People (requirements S7.7): someone in a user's life, who need not be a user of the server,
kept on the owner's own list, with their occasions; and the gifts given them or received from
them (S7.8). A 529's beneficiary is one of them (S1.8.1)."""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Integer,
    PrimaryKeyConstraint,
    Text,
    text,
)

from ..types import Dec
from ._base import pairs, record

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

# A dated occasion of a person's: an anniversary, a holiday they get gifts for (its date from
# the shipped list), or a custom one; each may have its own gift budget (S7.7.1).
Occasion = record(
    "Occasion",
    "Occsn",
    Column("personId", Text, ForeignKey("Person.id", ondelete="CASCADE"), nullable=False),
    Column("kind", Text, nullable=False),
    Column("name", Text),  # an anniversary's or a custom occasion's
    Column("holiday", Text),  # a shipped holiday's key
    Column("month", Integer),
    Column("day", Integer),
    Column("year", Integer),  # an anniversary's first year, for its count
    Column("budget", Dec),
    CheckConstraint("kind IN ('anniversary', 'holiday', 'custom')", name="kind"),
    CheckConstraint("(kind = 'holiday') = (holiday IS NOT NULL)", name="holiday"),
    CheckConstraint(
        "kind = 'holiday' OR (month BETWEEN 1 AND 12 AND day BETWEEN 1 AND 31)", name="date"
    ),
    Index("ix_Occasion_personId", "personId"),
)

# A gift, from idea to given, for one or more people and an occasion of a year; or one received
# from someone (S7.8). Its cost is linked to a transaction or typed.
Gift = record(
    "Gift",
    "Gift",
    Column("ownerId", Text, ForeignKey("User.id"), nullable=False),
    Column("occasion", Text),  # birthday, holiday:<key>, occasion:<id>; none for an idea
    Column("occasionYear", Integer),
    Column("description", Text, nullable=False),
    Column("status", Text, nullable=False, server_default=text("'idea'")),
    Column("cost", Dec),
    Column("transactionId", Text, ForeignKey("Transaction.id", ondelete="SET NULL")),
    Column("store", Text),  # where it was bought
    Column("link", Text),
    Column("notes", Text),
    Column("cash", Boolean, nullable=False, server_default=text("0")),  # money, for Form 709
    Column("thankYou", Boolean, nullable=False, server_default=text("0")),  # a received one's
    CheckConstraint("status IN ('idea', 'planned', 'bought', 'given', 'received')", name="status"),
    Index("ix_Gift_ownerId", "ownerId"),
)

# Who a gift is for, or for a received one, who it came from.
GiftPersons = pairs(
    "GiftPersons",
    Column("giftId", Text, ForeignKey("Gift.id", ondelete="CASCADE"), nullable=False),
    Column("personId", Text, ForeignKey("Person.id", ondelete="CASCADE"), nullable=False),
    PrimaryKeyConstraint("giftId", "personId"),
    Index("ix_GiftPersons_personId", "personId"),
)
