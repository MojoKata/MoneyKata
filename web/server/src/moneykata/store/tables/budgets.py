"""Budgets (requirements S7.1–S7.5): a user's plan per category over chosen accounts, shared
with a group at write for a household budget."""

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

from ..types import Cents, Day
from ._base import pairs, record, unique_live

Budget = record(
    "Budget",
    "Bdgt",
    Column("ownerId", Text, ForeignKey("User.id"), nullable=False),
    Column("name", Text, nullable=False),
    Index("ix_Budget_ownerId", "ownerId"),
)

BudgetAccounts = pairs(
    "BudgetAccounts",
    Column("budgetId", Text, ForeignKey("Budget.id", ondelete="CASCADE"), nullable=False),
    Column("accountId", Text, ForeignKey("Account.id", ondelete="CASCADE"), nullable=False),
    PrimaryKeyConstraint("budgetId", "accountId"),
)

# One category's plan from a month on. A change to the plan starts a new line from the month
# it is made in, so past months keep the plan they had.
BudgetLine = record(
    "BudgetLine",
    "BdgLn",
    Column("budgetId", Text, ForeignKey("Budget.id", ondelete="CASCADE"), nullable=False),
    Column("categoryId", Text, ForeignKey("Category.id"), nullable=False),
    Column("fromMonth", Day, nullable=False),
    Column("amount", Cents, nullable=False),
    Column("cadence", Text, nullable=False, server_default=text("'month'")),
    Column("rollover", Boolean, nullable=False, server_default=text("0")),
    CheckConstraint("cadence IN ('month', 'year')", name="cadence"),
    CheckConstraint("strftime('%d', \"fromMonth\") = '01'", name="from_month"),
    Index("ix_BudgetLine_budgetId", "budgetId"),
)
unique_live(BudgetLine, "budgetId", "categoryId", "fromMonth")
