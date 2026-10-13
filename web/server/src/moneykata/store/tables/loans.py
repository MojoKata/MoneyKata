"""Loans (requirements S1.9): a loan account's terms, from which its schedule is computed, and
the payoff planner's saved plans (S6.10)."""

from sqlalchemy import Boolean, CheckConstraint, Column, ForeignKey, Integer, Text, text

from ..types import Day, Dec
from ._base import record, unique_live

Loan = record(
    "Loan",
    "Loan",
    Column("accountId", Text, ForeignKey("Account.id", ondelete="CASCADE"), nullable=False),
    Column("principal", Dec, nullable=False),
    Column("startDate", Day, nullable=False),
    Column("termMonths", Integer, nullable=False),
    Column("rate", Dec, nullable=False),  # yearly, in percent
    # monthly amortization, or simple interest accrued daily (most car loans)
    Column("method", Text, nullable=False, server_default=text("'amortized'")),
    # Typed when the servicer's differs from the computed one.
    Column("payment", Dec),
    Column("escrowTax", Dec),  # a month, in the payment
    Column("escrowInsurance", Dec),
    Column("pmi", Dec),
    # A HELOC's draw period, paying interest only.
    Column("drawMonths", Integer),
    # An ARM's resets [{date, rate}], recasts [{date, fee}], each typed when known.
    Column("resets", Text, nullable=False, server_default=text("'[]'")),
    Column("recasts", Text, nullable=False, server_default=text("'[]'")),
    # For a mortgage, the original value of the home (for when PMI can go).
    Column("originalValue", Dec),
    # The property or vehicle it is secured by, for equity and loan-to-value (S1.9.5).
    Column("securedById", Text, ForeignKey("Item.id", ondelete="SET NULL")),
    CheckConstraint("method IN ('amortized', 'daily')", name="method"),
    CheckConstraint('"termMonths" > 0', name="term"),
)
unique_live(Loan, "accountId")

# A saved overpayment plan for one loan; at most one is the plan being followed, tracked from
# the day it was chosen.
PayoffPlan = record(
    "PayoffPlan",
    "Pyoff",
    Column("accountId", Text, ForeignKey("Account.id", ondelete="CASCADE"), nullable=False),
    Column("name", Text, nullable=False),
    Column("inputs", Text, nullable=False),  # JSON: the plan's overpayments
    Column("following", Boolean, nullable=False, server_default=text("0")),
    Column("followingSince", Day),
    Column("createdById", Text, ForeignKey("User.id")),
)
