"""529 plans (requirements S1.8): a 529 account's plan and beneficiary, who each contribution
came from, and the qualified expenses its withdrawals are matched with."""

from sqlalchemy import Boolean, CheckConstraint, Column, ForeignKey, Index, Integer, Text, text

from ..types import Day, Dec
from ._base import record, unique_live

EducationPlan = record(
    "EducationPlan",
    "EdPln",
    Column("accountId", Text, ForeignKey("Account.id", ondelete="CASCADE"), nullable=False),
    Column("planState", Text),  # the sponsoring state: Utah, Nevada…
    Column("planName", Text),  # my529, Bright Start…
    # The beneficiary: a person on the owner's list, or a user.
    Column("beneficiaryPersonId", Text, ForeignKey("Person.id")),
    Column("beneficiaryUserId", Text, ForeignKey("User.id")),
    Column("openedOn", Day),
    Column("stateDeduction", Dec),  # what the owner expects a year, typed (S8.18)
    CheckConstraint(
        '"beneficiaryPersonId" IS NULL OR "beneficiaryUserId" IS NULL', name="one_beneficiary"
    ),
)
unique_live(EducationPlan, "accountId")

# Who a contribution (a deposit into a 529) came from: the owner (neither set), a user or a
# person; a five-year election spreads it over five years of gift exclusions (S1.8.2).
Contribution = record(
    "Contribution",
    "Cntrb",
    Column("transactionId", Text, ForeignKey("Transaction.id", ondelete="CASCADE"), nullable=False),
    Column("fromUserId", Text, ForeignKey("User.id")),
    Column("fromPersonId", Text, ForeignKey("Person.id")),
    Column("fiveYear", Boolean, nullable=False, server_default=text("0")),
    CheckConstraint('"fromUserId" IS NULL OR "fromPersonId" IS NULL', name="one_contributor"),
)
unique_live(Contribution, "transactionId")

# A qualified education expense a 529's withdrawals are matched with (S1.8.3).
QualifiedExpense = record(
    "QualifiedExpense",
    "QExpn",
    Column("accountId", Text, ForeignKey("Account.id", ondelete="CASCADE"), nullable=False),
    Column("date", Day, nullable=False),
    Column("year", Integer, nullable=False),  # the tax year it counts in
    Column("kind", Text, nullable=False),
    Column("description", Text),
    Column("amount", Dec, nullable=False),
    Column("transactionId", Text, ForeignKey("Transaction.id")),  # how it was paid, if recorded
    CheckConstraint(
        "kind IN ('tuition', 'room-board', 'books', 'computer', 'k12', 'apprenticeship', "
        "'student-loan')",
        name="kind",
    ),
    CheckConstraint("amount > 0", name="amount"),
    Index("ix_QualifiedExpense_account", "accountId", "year"),
)
