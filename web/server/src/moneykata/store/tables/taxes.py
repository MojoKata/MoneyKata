"""Tax books (requirements S8.14–S8.17): one tax year's record for a user or a married couple,
the accounts it counts, its filings with their estimated payments, and its tax documents."""

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

from ..types import Cents, Day, Dec, UtcTimestamp
from ._base import pairs, record, unique_live

TaxBook = record(
    "TaxBook",
    "TaxBk",
    Column("ownerId", Text, ForeignKey("User.id"), nullable=False),  # who made it
    Column("year", Integer, nullable=False),
    # Bitcoin network fees on transfers between the owner's own accounts (S8.19): a sale, the
    # default, or not taxed, as a preparer may read them.
    Column("bitcoinFees", Text, nullable=False, server_default=text("'sale'")),
    # Made from last year's book: what it copies waits until every filer has accepted (S8.14.4).
    Column("fromLastYear", Boolean, nullable=False, server_default=text("0")),
    CheckConstraint("\"bitcoinFees\" IN ('sale', 'not-taxed')", name="bitcoin_fees"),
    Index("ix_TaxBook_owner", "ownerId", "year"),
)

# Its filers: one user, or two who are married; one named by someone else accepts first.
TaxBookFilers = pairs(
    "TaxBookFilers",
    Column("bookId", Text, ForeignKey("TaxBook.id", ondelete="CASCADE"), nullable=False),
    Column("userId", Text, ForeignKey("User.id"), nullable=False),
    Column("acceptedAt", UtcTimestamp),
    PrimaryKeyConstraint("bookId", "userId"),
    Index("ix_TaxBookFilers_user", "userId"),
)

# Changes to the accounts it counts: one added (a custodial account) or one left out.
TaxBookAccounts = pairs(
    "TaxBookAccounts",
    Column("bookId", Text, ForeignKey("TaxBook.id", ondelete="CASCADE"), nullable=False),
    Column("accountId", Text, ForeignKey("Account.id", ondelete="CASCADE"), nullable=False),
    Column("counted", Boolean, nullable=False),
    # The filer who added it: an added account counts only while they can see it (S8.14.2).
    Column("addedById", Text, ForeignKey("User.id")),
    PrimaryKeyConstraint("bookId", "accountId"),
)

# A person the filers claim for the year (S8.14.5): how they are claimed, the months they
# lived with the filers, and whether a full-time student. MoneyKata doesn't decide who qualifies.
TaxBookDependent = record(
    "TaxBookDependent",
    "TxDep",
    Column("bookId", Text, ForeignKey("TaxBook.id", ondelete="CASCADE"), nullable=False),
    Column("personId", Text, ForeignKey("Person.id"), nullable=False),
    Column("claimedAs", Text, nullable=False),
    Column("months", Integer, nullable=False, server_default=text("12")),
    Column("student", Boolean, nullable=False, server_default=text("0")),
    CheckConstraint(
        "\"claimedAs\" IN ('qualifying child', 'qualifying relative')", name="claimed_as"
    ),
    CheckConstraint("months BETWEEN 0 AND 12", name="months"),
    Index("ix_TaxBookDependent_bookId", "bookId"),
)
unique_live(TaxBookDependent, "bookId", "personId")

# The counted accounts in a dependent's name (a custodial account), for Form 8615 (S8.14.5.3).
TaxDependentAccounts = pairs(
    "TaxDependentAccounts",
    Column(
        "dependentId",
        Text,
        ForeignKey("TaxBookDependent.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("accountId", Text, ForeignKey("Account.id", ondelete="CASCADE"), nullable=False),
    PrimaryKeyConstraint("dependentId", "accountId"),
)

# One return: federal, a state's or a locality's; an amended return names the one it amends.
Filing = record(
    "Filing",
    "Filng",
    Column("bookId", Text, ForeignKey("TaxBook.id", ondelete="CASCADE"), nullable=False),
    Column("jurisdiction", Text, nullable=False),  # federal, state, local
    Column("place", Text),  # the state or locality
    Column("form", Text, nullable=False),
    Column("amendsId", Text, ForeignKey("Filing.id")),
    Column("filingStatus", Text),  # as typed: MoneyKata never chooses it
    Column("preparedBy", Text),
    Column("sentBy", Text),  # e-file or paper
    Column("progress", Text, nullable=False, server_default=text("'not started'")),
    Column("dueDate", Day),
    Column("extensionFiledOn", Day),
    Column("extendedDue", Day),
    Column("filedOn", Day),
    Column("confirmation", Text),
    Column("resultKind", Text),  # refund, owed, none
    Column("resultAmount", Cents),
    Column("resultTransactionId", Text, ForeignKey("Transaction.id", ondelete="SET NULL")),
    # Figures next year needs, typed from the return as filed (S8.17), as JSON.
    Column("carried", Text, nullable=False, server_default=text("'{}'")),
    CheckConstraint("jurisdiction IN ('federal', 'state', 'local')", name="jurisdiction"),
    CheckConstraint(
        "progress IN ('not started', 'in progress', 'filed', 'accepted', 'rejected')",
        name="progress",
    ),
    CheckConstraint("\"sentBy\" IS NULL OR \"sentBy\" IN ('e-file', 'paper')", name="sent_by"),
    CheckConstraint(
        "\"resultKind\" IS NULL OR \"resultKind\" IN ('refund', 'owed', 'none')",
        name="result_kind",
    ),
    Index("ix_Filing_bookId", "bookId"),
)

# A filing's estimated payment for a quarter, matched to the transaction that paid it.
EstimatedPayment = record(
    "EstimatedPayment",
    "EstPy",
    Column("filingId", Text, ForeignKey("Filing.id", ondelete="CASCADE"), nullable=False),
    Column("quarter", Integer, nullable=False),
    Column("dueDate", Day),
    Column("amount", Dec, nullable=False),
    Column("paidOn", Day),
    Column("transactionId", Text, ForeignKey("Transaction.id", ondelete="SET NULL")),
    CheckConstraint("quarter BETWEEN 1 AND 4", name="quarter"),
    Index("ix_EstimatedPayment_filingId", "filingId"),
)

# A tax document: received (a W-2, a 1099) in the book, or filed (the return as filed, a
# notice) in a filing; its file is kept as a receipt.
TaxDocument = record(
    "TaxDocument",
    "TxDoc",
    Column("bookId", Text, ForeignKey("TaxBook.id", ondelete="CASCADE"), nullable=False),
    Column("filingId", Text, ForeignKey("Filing.id", ondelete="CASCADE")),
    Column("direction", Text, nullable=False),  # received or filed
    Column("form", Text, nullable=False),
    Column("issuer", Text),
    Column("accountId", Text, ForeignKey("Account.id", ondelete="SET NULL")),
    Column("receiptId", Text, ForeignKey("Receipt.id", ondelete="SET NULL")),
    Column("notes", Text),
    CheckConstraint("direction IN ('received', 'filed')", name="direction"),
    CheckConstraint("direction = 'received' OR \"filingId\" IS NOT NULL", name="filed_in"),
    Index("ix_TaxDocument_bookId", "bookId"),
)
