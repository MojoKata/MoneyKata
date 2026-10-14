"""529 plans (requirements S1.8) and the people they are for (S7.7): the plan and its
beneficiary, contributions and who made them against the annual gift exclusion, withdrawals
against qualified expenses with their receipts, the Roth IRA rollover, and the Goal tab's
education projection (S6.2.2)."""

import datetime as dt
import json
from decimal import Decimal

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import false, select

from .. import access, activity, clock, education, ids, projections, receipts
from ..errors import FieldError, Problem, refuse
from ..store.entities.accounts import Account, Transaction
from ..store.entities.education import Contribution, EducationPlan, Person, QualifiedExpense
from ..store.entities.projections import Projection
from ..store.entities.users import User
from .conventions import Model, Money
from .deps import Caller, caller, server
from .projections import ProjectionDetail
from .projections import detail as projection_detail
from .receipts import ReceiptRow
from .receipts import row as receipt_row

router = APIRouter(prefix="/ui/api", tags=["education"])


# ---- People (S7.7): the list Gifts builds on ----


class PersonIn(Model):
    name: str
    relationship: str | None = None
    userId: str | None = None
    birthMonth: int | None = None
    birthDay: int | None = None
    birthYear: int | None = None


class PersonOut(Model):
    id: str
    name: str
    relationship: str | None
    userId: str | None
    birthMonth: int | None
    birthDay: int | None
    birthYear: int | None
    version: int


def person_out(p: Person) -> PersonOut:
    return PersonOut(
        id=p.id,
        name=p.name,
        relationship=p.relationship,
        userId=p.userId,
        birthMonth=p.birthMonth,
        birthDay=p.birthDay,
        birthYear=p.birthYear,
        version=p.version,
    )


def check_person(body: PersonIn) -> dict:
    e = []
    name = body.name.strip()
    if not name or len(name) > 80:
        e.append(FieldError("name", "name-invalid", "A name, up to 80 characters."))
    if body.birthMonth is not None and not 1 <= body.birthMonth <= 12:
        e.append(FieldError("birthMonth", "month-invalid", "A month, 1 to 12."))
    if body.birthDay is not None and not 1 <= body.birthDay <= 31:
        e.append(FieldError("birthDay", "day-invalid", "A day, 1 to 31."))
    year = clock.today().year
    if body.birthYear is not None and not year - 120 <= body.birthYear <= year:
        e.append(FieldError("birthYear", "year-invalid", "A year of birth."))
    if e:
        raise Problem(422, e[0].code, e[0].message, e)
    return {
        "name": name,
        "relationship": (body.relationship or "").strip() or None,
        "userId": body.userId or None,
        "birthMonth": body.birthMonth,
        "birthDay": body.birthDay,
        "birthYear": body.birthYear,
    }


def people_of(s, user_id: str) -> list[Person]:
    return list(
        s.scalars(
            select(Person)
            .where(Person.ownerId == user_id, Person.deleted == false())
            .order_by(Person.name)
        )
    )


@router.get("/people", response_model=list[PersonOut])
def list_people(request: Request, c: Caller = Depends(caller)):
    """The caller's own list of people: nobody else's."""
    with server(request).db.read() as s:
        return [person_out(p) for p in people_of(s, c.id)]


@router.post("/people", response_model=PersonOut, status_code=201)
def add_person(body: PersonIn, request: Request, c: Caller = Depends(caller)):
    values = check_person(body)
    with server(request).db.tx() as s:
        if values["userId"] and s.get(User, values["userId"]) is None:
            raise refuse("userId", "user-unknown", "No such user.")
        p = Person(id=ids.new_id("Persn"), ownerId=c.id, **values)
        s.add(p)
        s.flush()
        return person_out(p)


# ---- The plan ----


class BeneficiaryRef(Model):
    kind: str  # person or user
    id: str


class BeneficiaryOut(BeneficiaryRef):
    name: str
    birthYear: int | None


class PlanIn(Model):
    planState: str | None = None
    planName: str | None = None
    beneficiary: BeneficiaryRef | None = None
    openedOn: dt.date | None = None
    stateDeduction: Money | None = None


class RolloverOut(Model):
    possibleFrom: dt.date | None
    limit: Money
    used: Money
    eligible: Money
    available: Money


class PlanOut(Model):
    planState: str | None
    planName: str | None
    beneficiary: BeneficiaryOut | None
    openedOn: dt.date | None
    stateDeduction: Money | None
    contributedThisYear: Money
    rollover: RolloverOut
    canWrite: bool


def _account(s, c: Caller, account_id: str, need: str = "read") -> tuple[Account, str]:
    a, lvl = access.account(s, c.id, account_id, need)
    if a.type != "529":
        raise Problem(409, "not-a-529", "This account isn't a 529 plan.")
    return a, lvl


def _beneficiary_out(b: education.Beneficiary | None) -> BeneficiaryOut | None:
    if b is None:
        return None
    return BeneficiaryOut(kind=b.kind, id=b.id, name=b.name, birthYear=b.birthYear)


def plan_view(s, a: Account, lvl: str) -> PlanOut:
    today = clock.today()
    plan = education.plan_of(s, a)
    rows = education.contributions(s, a)
    r = education.rollover(s, a, plan, rows, today)
    return PlanOut(
        planState=plan.planState if plan else None,
        planName=plan.planName if plan else None,
        beneficiary=_beneficiary_out(education.beneficiary(s, plan)),
        openedOn=plan.openedOn if plan else None,
        stateDeduction=plan.stateDeduction if plan else None,
        contributedThisYear=sum((x.amount for x in rows if x.date.year == today.year), Decimal(0)),
        rollover=RolloverOut(**r.__dict__),
        canWrite=lvl in ("owner", "write"),
    )


def _check_beneficiary(s, c: Caller, b: BeneficiaryRef | None, owner_id: str) -> dict:
    if b is None:
        return {"beneficiaryPersonId": None, "beneficiaryUserId": None}
    if b.kind == "person":
        p = s.get(Person, b.id)
        if p is None or p.deleted or p.ownerId != owner_id:
            raise refuse("beneficiary", "beneficiary-invalid", "A person on the owner's list.")
        return {"beneficiaryPersonId": p.id, "beneficiaryUserId": None}
    if b.kind == "user" and s.get(User, b.id) is not None:
        return {"beneficiaryPersonId": None, "beneficiaryUserId": b.id}
    raise refuse("beneficiary", "beneficiary-invalid", "A person or a user.")


@router.get("/accounts/{account_id}/plan529", response_model=PlanOut)
def get_plan(account_id: str, request: Request, c: Caller = Depends(caller)):
    with server(request).db.read() as s:
        a, lvl = _account(s, c, account_id)
        return plan_view(s, a, lvl)


@router.put("/accounts/{account_id}/plan529", response_model=PlanOut)
def put_plan(account_id: str, body: PlanIn, request: Request, c: Caller = Depends(caller)):
    if body.stateDeduction is not None and body.stateDeduction < 0:
        raise refuse("stateDeduction", "amount-invalid", "Zero or more.")
    if body.openedOn is not None and body.openedOn > clock.today():
        raise refuse("openedOn", "date-ahead", "Not after today.")
    with server(request).db.tx() as s:
        a, lvl = _account(s, c, account_id, "write")
        values = {
            "planState": (body.planState or "").strip() or None,
            "planName": (body.planName or "").strip() or None,
            "openedOn": body.openedOn,
            "stateDeduction": body.stateDeduction,
            **_check_beneficiary(s, c, body.beneficiary, a.ownerId),
        }
        plan = education.plan_of(s, a)
        if plan is None:
            s.add(EducationPlan(id=ids.new_id("EdPln"), accountId=a.id, **values))
        else:
            for k, v in values.items():
                setattr(plan, k, v)
            plan.updatedAt = clock.now()
        s.flush()
        activity.record(
            s,
            "account.updated",
            actor=c.id,
            subject_kind="account",
            subject_id=a.id,
            owner=a.ownerId,
            detail={"fields": ["plan"]},
        )
        return plan_view(s, a, lvl)


# ---- Contributions (S1.8.2) ----


class ContributionOut(Model):
    transactionId: str
    date: dt.date
    amount: Money
    contributor: str
    name: str
    relationship: str | None
    fiveYear: bool


class GiftYearOut(Model):
    contributor: str
    name: str
    year: int
    counted: Money
    exclusion: Money
    over: bool
    fromElection: int | None


class ContributionsView(Model):
    rows: list[ContributionOut]
    years: list[GiftYearOut]
    canWrite: bool


class ContributionIn(Model):
    date: dt.date
    amount: Money
    contributor: str = "owner"  # owner, user:<id> or person:<id>
    fiveYear: bool = False
    fromAccountId: str | None = None  # its half of the transfer is made too


class TagIn(Model):
    contributor: str = "owner"
    fiveYear: bool = False


def _contributor(s, c: Caller, key: str, owner_id: str) -> tuple[str | None, str | None]:
    if key == "owner":
        return None, None
    kind, _, ident = key.partition(":")
    if kind == "user" and s.get(User, ident) is not None:
        return ident, None
    if kind == "person":
        p = s.get(Person, ident)
        if p is not None and not p.deleted and p.ownerId == owner_id:
            return None, p.id
    raise refuse("contributor", "contributor-invalid", "The owner, a user or a person.")


def contributions_view(s, a: Account, lvl: str) -> ContributionsView:
    rows = education.contributions(s, a)
    return ContributionsView(
        rows=[ContributionOut(**r.__dict__) for r in reversed(rows)],
        years=[GiftYearOut(**g.__dict__) for g in education.gift_years(s, rows)],
        canWrite=lvl in ("owner", "write"),
    )


def _tag(s, txn_id: str, from_user, from_person, five: bool) -> None:
    row = s.scalars(
        select(Contribution).where(
            Contribution.transactionId == txn_id, Contribution.deleted == false()
        )
    ).first()
    if row is None:
        s.add(
            Contribution(
                id=ids.new_id("Cntrb"),
                transactionId=txn_id,
                fromUserId=from_user,
                fromPersonId=from_person,
                fiveYear=five,
            )
        )
    else:
        row.fromUserId, row.fromPersonId, row.fiveYear = from_user, from_person, five
        row.updatedAt = clock.now()


@router.get("/accounts/{account_id}/contributions", response_model=ContributionsView)
def list_contributions(account_id: str, request: Request, c: Caller = Depends(caller)):
    with server(request).db.read() as s:
        a, lvl = _account(s, c, account_id)
        return contributions_view(s, a, lvl)


@router.post(
    "/accounts/{account_id}/contributions", response_model=ContributionsView, status_code=201
)
def add_contribution(
    account_id: str, body: ContributionIn, request: Request, c: Caller = Depends(caller)
):
    """A deposit into the 529, with who made it; from a bank account, both halves."""
    if body.amount <= 0:
        raise refuse("amount", "amount-invalid", "More than zero.")
    with server(request).db.tx() as s:
        a, lvl = _account(s, c, account_id, "write")
        from_user, from_person = _contributor(s, c, body.contributor, a.ownerId)
        other = None
        if body.fromAccountId:
            access.account(s, c.id, body.fromAccountId, "write")
            other = Transaction(
                id=ids.new_id("Txn"),
                accountId=body.fromAccountId,
                date=body.date,
                kind="transfer",
                amount=-body.amount,
                payee=a.name,
                createdById=c.id,
            )
            s.add(other)
        txn = Transaction(
            id=ids.new_id("Txn"),
            accountId=a.id,
            date=body.date,
            kind="transfer" if other else "deposit",
            amount=body.amount,
            payee="Contribution",
            createdById=c.id,
        )
        s.add(txn)
        s.flush()
        if other is not None:
            txn.transferId, other.transferId = other.id, txn.id
        _tag(s, txn.id, from_user, from_person, body.fiveYear)
        s.flush()
        activity.record(
            s,
            "529.contribution",
            actor=c.id,
            subject_kind="account",
            subject_id=a.id,
            owner=a.ownerId,
        )
        return contributions_view(s, a, lvl)


@router.put("/contributions/{transaction_id}", response_model=ContributionsView)
def tag_contribution(
    transaction_id: str, body: TagIn, request: Request, c: Caller = Depends(caller)
):
    """Who an existing deposit (an imported one) came from, and whether it is a five-year
    election."""
    with server(request).db.tx() as s:
        t = s.get(Transaction, transaction_id)
        if t is None or t.deleted or t.amount <= 0:
            raise Problem(404, "not-found", "No such contribution.")
        a, lvl = _account(s, c, t.accountId, "write")
        from_user, from_person = _contributor(s, c, body.contributor, a.ownerId)
        _tag(s, t.id, from_user, from_person, body.fiveYear)
        s.flush()
        return contributions_view(s, a, lvl)


# ---- Withdrawals and qualified expenses (S1.8.3) ----


class ExpenseIn(Model):
    date: dt.date
    year: int | None = None  # the tax year it counts in: the date's, unless said
    kind: str
    description: str | None = None
    amount: Money


class ExpenseOut(Model):
    id: str
    date: dt.date
    year: int
    kind: str
    kindLabel: str
    description: str | None
    amount: Money
    documents: list[ReceiptRow]


class WithdrawalYearOut(Model):
    year: int
    distributions: Money
    expenses: Money
    notCovered: Money


class WithdrawalsView(Model):
    years: list[WithdrawalYearOut]
    expenses: list[ExpenseOut]
    kinds: list[tuple[str, str]]
    canWrite: bool


class DocumentIn(Model):
    receiptId: str


def withdrawals_view(s, c: Caller, a: Account, lvl: str) -> WithdrawalsView:
    return WithdrawalsView(
        years=[WithdrawalYearOut(**w.__dict__) for w in education.withdrawals(s, a)],
        expenses=[
            ExpenseOut(
                id=e.id,
                date=e.date,
                year=e.year,
                kind=e.kind,
                kindLabel=education.KINDS[e.kind],
                description=e.description,
                amount=e.amount,
                documents=[
                    receipt_row(s, r, receipts.level(s, c.id, r) or "read")
                    for r in receipts.of_item(s, e.id, "expense")
                ],
            )
            for e in education.expenses(s, a)
        ],
        kinds=list(education.KINDS.items()),
        canWrite=lvl in ("owner", "write"),
    )


@router.get("/accounts/{account_id}/withdrawals", response_model=WithdrawalsView)
def list_withdrawals(account_id: str, request: Request, c: Caller = Depends(caller)):
    with server(request).db.read() as s:
        a, lvl = _account(s, c, account_id)
        return withdrawals_view(s, c, a, lvl)


@router.post("/accounts/{account_id}/expenses", response_model=WithdrawalsView, status_code=201)
def add_expense(account_id: str, body: ExpenseIn, request: Request, c: Caller = Depends(caller)):
    if body.kind not in education.KINDS:
        raise refuse("kind", "kind-invalid", "One of the qualified expenses.")
    if body.amount <= 0:
        raise refuse("amount", "amount-invalid", "More than zero.")
    with server(request).db.tx() as s:
        a, lvl = _account(s, c, account_id, "write")
        s.add(
            QualifiedExpense(
                id=ids.new_id("QExpn"),
                accountId=a.id,
                date=body.date,
                year=body.year or body.date.year,
                kind=body.kind,
                description=(body.description or "").strip() or None,
                amount=body.amount,
            )
        )
        s.flush()
        return withdrawals_view(s, c, a, lvl)


def _expense(s, c: Caller, expense_id: str) -> tuple[QualifiedExpense, Account, str]:
    e = s.get(QualifiedExpense, expense_id)
    if e is None or e.deleted:
        raise Problem(404, "not-found", "No such expense.")
    a, lvl = _account(s, c, e.accountId, "write")
    return e, a, lvl


@router.delete("/expenses/{expense_id}", response_model=WithdrawalsView)
def delete_expense(expense_id: str, request: Request, c: Caller = Depends(caller)):
    with server(request).db.tx() as s:
        e, a, lvl = _expense(s, c, expense_id)
        e.mark_deleted(c.id)
        s.flush()
        return withdrawals_view(s, c, a, lvl)


@router.post("/expenses/{expense_id}/documents", response_model=WithdrawalsView)
def attach_receipt(
    expense_id: str, body: DocumentIn, request: Request, c: Caller = Depends(caller)
):
    with server(request).db.tx() as s:
        e, a, lvl = _expense(s, c, expense_id)
        r, _ = receipts.get(s, c.id, body.receiptId)
        receipts.attach_item(s, c.id, r, e, "expense")
        return withdrawals_view(s, c, a, lvl)


# ---- The Goal tab (S1.8.5) ----


class GoalView(Model):
    beneficiary: BeneficiaryOut | None
    projection: ProjectionDetail | None
    others: int  # more education projections for the same beneficiary


def _goals(s, c: Caller, b: education.Beneficiary) -> list[Projection]:
    out = []
    for p, _ in projections.visible(s, c.id):
        if p.goal != "education":
            continue
        who = json.loads(p.inputs or "{}").get("beneficiary") or {}
        if who.get("kind") == b.kind and who.get("id") == b.id:
            out.append(p)
    return sorted(out, key=lambda p: (not p.active, p.createdAt))


@router.get("/accounts/{account_id}/goal", response_model=GoalView)
def get_goal(account_id: str, request: Request, c: Caller = Depends(caller)):
    """The beneficiary's education projection: the active one, else the first made."""
    with server(request).db.read() as s:
        a, _ = _account(s, c, account_id)
        b = education.beneficiary(s, education.plan_of(s, a))
        if b is None:
            return GoalView(beneficiary=None, projection=None, others=0)
        found = _goals(s, c, b)
        if not found:
            return GoalView(beneficiary=_beneficiary_out(b), projection=None, others=0)
        p = found[0]
        lvl = access.level_of(s, c.id, "projection", p.ownerId, p.id, p.deleted) or "read"
        return GoalView(
            beneficiary=_beneficiary_out(b),
            projection=projection_detail(s, c.id, p, lvl),
            others=len(found) - 1,
        )


@router.post("/accounts/{account_id}/goal", response_model=GoalView, status_code=201)
def start_goal(account_id: str, request: Request, c: Caller = Depends(caller)):
    """An education projection for the beneficiary, built on their 529s the caller can see,
    starting from the shipped public-college average and this year's contributions."""
    with server(request).db.tx() as s:
        a, _ = _account(s, c, account_id, "write")
        b = education.beneficiary(s, education.plan_of(s, a))
        if b is None:
            raise Problem(409, "no-beneficiary", "Choose the beneficiary in Settings first.")
        mine = [x.id for x, _ in access.visible_accounts(s, c.id)]
        built = education.accounts_for(s, b.kind, b.id, mine) or [a.id]
        rows = education.contributions(s, a)
        year = clock.today().year
        recent = sum((r.amount for r in rows if r.date.year >= year - 1), Decimal(0))
        p = Projection(
            id=ids.new_id("Prjct"),
            ownerId=c.id,
            name=f"{b.name.split(' ')[0]}'s college",
            goal="education",
            builtOn=json.dumps({"kind": "accounts", "ids": built}),
            inputs=json.dumps(
                {
                    "beneficiary": {"kind": b.kind, "id": b.id},
                    "startAge": 18,
                    "schoolYears": 4,
                    "costBasis": "public",
                    "monthly": round(float(recent) / 24, 2),
                }
            ),
        )
        s.add(p)
        s.flush()
        activity.record(
            s,
            "projection.created",
            actor=c.id,
            subject_kind="projection",
            subject_id=p.id,
            owner=c.id,
        )
        return GoalView(
            beneficiary=_beneficiary_out(b),
            projection=projection_detail(s, c.id, p, "owner"),
            others=0,
        )


@router.delete("/people/{person_id}", status_code=204)
def delete_person(person_id: str, request: Request, c: Caller = Depends(caller)):
    with server(request).db.tx() as s:
        p = s.get(Person, person_id)
        if p is None or p.deleted or p.ownerId != c.id:
            raise Problem(404, "not-found", "Not found")
        p.mark_deleted(c.id)
    return Response(status_code=204)
