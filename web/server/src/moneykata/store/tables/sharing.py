"""Portfolios and shares (requirements §8.1, §13.3–§13.7)."""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    PrimaryKeyConstraint,
    Text,
    text,
)

from ._base import pairs, record

Portfolio = record(
    "Portfolio",
    "Portf",
    Column("ownerId", Text, ForeignKey("User.id"), nullable=False),
    Column("name", Text, nullable=False),
    # What Performance compares it with: a symbol (SPY, VT) or "60-40" (VT and BND).
    Column("benchmark", Text, nullable=False, server_default=text("'VT'")),
    Column("notes", Text),
    Index("ix_Portfolio_ownerId", "ownerId"),
)

PortfolioAccounts = pairs(
    "PortfolioAccounts",
    Column("portfolioId", Text, ForeignKey("Portfolio.id", ondelete="CASCADE"), nullable=False),
    Column("accountId", Text, ForeignKey("Account.id", ondelete="CASCADE"), nullable=False),
    PrimaryKeyConstraint("portfolioId", "accountId"),
)

# A grant of one item, at one level, to a user or a group (§13.3). Items of the other shareable
# kinds join "account" and "portfolio" as they are built.
Share = record(
    "Share",
    "Share",
    Column("kind", Text, nullable=False),
    Column("itemId", Text, nullable=False),
    Column("userId", Text, ForeignKey("User.id", ondelete="CASCADE")),
    Column("groupId", Text, ForeignKey("Group.id", ondelete="CASCADE")),
    Column("level", Text, nullable=False),
    Column("createdById", Text, ForeignKey("User.id")),
    CheckConstraint("kind IN ('account', 'portfolio')", name="kind"),
    CheckConstraint("level IN ('read', 'write')", name="level"),
    CheckConstraint('("userId" IS NULL) != ("groupId" IS NULL)', name="one_grantee"),
    Index("ix_Share_item", "kind", "itemId"),
    Index("ix_Share_userId", "userId"),
    Index("ix_Share_groupId", "groupId"),
)

# A receiver's "Count in my totals" on an account shared with them (§13.7).
CountedAccounts = pairs(
    "CountedAccounts",
    Column("userId", Text, ForeignKey("User.id", ondelete="CASCADE"), nullable=False),
    Column("accountId", Text, ForeignKey("Account.id", ondelete="CASCADE"), nullable=False),
    Column("counted", Boolean, nullable=False, server_default=text("1")),
    PrimaryKeyConstraint("userId", "accountId"),
)
