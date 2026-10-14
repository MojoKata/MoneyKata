"""Dev mode's 529 (requirements S17.7): Alice's daughter Emma and her grandmother Margaret on
Alice's list of people, Emma's 529 with Alice's monthly contributions, Margaret's five-year
election and one from Bob, invested in a fund, and Emma's education projection, active."""

import datetime as dt
import json
from decimal import Decimal as D

from .. import clock, ids, projections
from ..prices.stub import walk
from ..store.entities.accounts import Account
from ..store.entities.education import Contribution, EducationPlan, Person
from ..store.entities.projections import Projection
from ..store.repos import ledger as repo
from .seed_accounts import Book


def seed_education(s, people: dict) -> None:
    alice, bob = people["alice"], people["bob"]
    today = clock.today()
    b = Book(s, today)
    emma = Person(
        id=ids.new_id("Persn"),
        ownerId=alice.id,
        name="Emma Griffin",
        relationship="child",
        birthMonth=10,
        birthDay=20,
        birthYear=2018,
        giftBudget=D(600),
        notes="Loves drawing and horses.",
    )
    margaret = Person(
        id=ids.new_id("Persn"),
        ownerId=alice.id,
        name="Margaret Griffin",
        relationship="grandmother",
        birthMonth=3,
        birthDay=14,
    )
    s.add_all([emma, margaret])
    acct = Account(
        id=ids.new_id("Acct"),
        ownerId=alice.id,
        name="Emma's 529",
        type="529",
        institution="my529",
        mask="2018",
        keptBy='["manual"]',
    )
    s.add(acct)
    s.flush()
    s.add(
        EducationPlan(
            id=ids.new_id("EdPln"),
            accountId=acct.id,
            planState="Utah",
            planName="my529",
            beneficiaryPersonId=emma.id,
            openedOn=dt.date(2018, 11, 2),
            stateDeduction=D(2410),
        )
    )

    def give(day, amount, user=None, person=None, five=False):
        t = b.txn(acct, day, amount, "Contribution", kind="deposit")
        s.flush()
        if user or person or five:
            s.add(
                Contribution(
                    id=ids.new_id("Cntrb"),
                    transactionId=t.id,
                    fromUserId=user.id if user else None,
                    fromPersonId=person.id if person else None,
                    fiveYear=five,
                )
            )
        return t

    give(dt.date(2018, 11, 2), "12000")
    give(dt.date(2024, 3, 1), "30000", person=margaret, five=True)
    give(dt.date(today.year - 1, 12, 20), "2500", user=bob)
    for month in b.months(11):
        if (day := b.day(month, 5)) is not None:
            give(day, "250")
    s.flush()
    fund = repo.instrument(s, "VTI", "Vanguard Total Stock Market ETF", "etf")
    for day, amount in ((dt.date(2018, 11, 5), 11500), (dt.date(2024, 3, 5), 29000)):
        price = walk("VTI", day if day >= dt.date(2020, 1, 1) else dt.date(2020, 1, 2))
        qty = (D(amount) / price).quantize(D("0.0001"))
        b.trade(acct, day, "buy", fund, qty, price)
    s.flush()
    p = Projection(
        id=ids.new_id("Prjct"),
        ownerId=alice.id,
        name="Emma's college",
        goal="education",
        builtOn=json.dumps({"kind": "accounts", "ids": [acct.id]}),
        inputs=json.dumps(
            {
                "beneficiary": {"kind": "person", "id": emma.id},
                "startAge": 18,
                "schoolYears": 4,
                "costBasis": "public",
                "monthly": 250,
                "fees": 0.1,
            }
        ),
    )
    s.add(p)
    s.flush()
    p.active = True
    p.baseline = json.dumps(projections.make_baseline(projections.compute(s, p, alice.id)))
    p.baselineAt = clock.now()
    acct.updatedAt = clock.now()
