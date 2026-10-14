import datetime as dt
from dataclasses import dataclass
from decimal import Decimal

from . import Record


@dataclass(kw_only=True, eq=False)
class Person(Record):
    id: str
    ownerId: str
    name: str
    relationship: str | None = None
    userId: str | None = None
    birthMonth: int | None = None
    birthDay: int | None = None
    birthYear: int | None = None
    giftBudget: Decimal | None = None
    leadDays: int = 14
    notes: str | None = None


@dataclass(kw_only=True, eq=False)
class EducationPlan(Record):
    id: str
    accountId: str
    planState: str | None = None
    planName: str | None = None
    beneficiaryPersonId: str | None = None
    beneficiaryUserId: str | None = None
    openedOn: dt.date | None = None
    stateDeduction: Decimal | None = None


@dataclass(kw_only=True, eq=False)
class Contribution(Record):
    id: str
    transactionId: str
    fromUserId: str | None = None
    fromPersonId: str | None = None
    fiveYear: bool = False


@dataclass(kw_only=True, eq=False)
class QualifiedExpense(Record):
    id: str
    accountId: str
    date: dt.date
    year: int
    kind: str
    amount: Decimal
    description: str | None = None
    transactionId: str | None = None
