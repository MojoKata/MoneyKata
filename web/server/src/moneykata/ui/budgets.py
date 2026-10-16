"""Budgets (requirements S7.1–S7.5): a budget's month, its plan, cash flow, trends and the
recurring transactions in its accounts. A budget is owned by a user and shared like an account;
a household budget is one shared with a group at write (S10.3)."""

import datetime as dt
from decimal import Decimal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import Field
from sqlalchemy import false, select

from .. import access, activity, budgets, clock, ids
from ..budgets import recurring
from ..errors import FieldError, Problem
from ..store.entities.accounts import Account, Category, Transaction
from ..store.entities.budgets import Budget, BudgetAccount, BudgetLine
from ..store.entities.users import User
from .conventions import Deleted, ExactRoute, Model, Money, check, gone, if_match, stale
from .deps import Caller, caller, server

router = APIRouter(prefix="/ui/api", route_class=ExactRoute, tags=["budgets"])


class BudgetRow(Model):
    id: str
    name: str
    ownerId: str
    ownerName: str
    level: str
    accountIds: list[str]
    sharedWith: int
    version: int


class NewBudget(Model):
    name: str
    accountIds: list[str] = Field(default_factory=list)


class BudgetChange(Model):
    name: str | None = None
    accountIds: list[str] | None = None


class PlanLine(Model):
    categoryId: str
    amount: Money
    cadence: str = "month"
    rollover: bool = False


class Plan(Model):
    """The plan from a month on: the categories listed, and none other."""

    month: dt.date
    lines: list[PlanLine]


class MonthRow(Model):
    categoryId: str
    label: str
    kind: str
    cadence: str
    rollover: bool
    planned: Money
    carried: Money
    actual: Money
    remaining: Money
    state: str


class Unplanned(Model):
    categoryId: str
    label: str
    spent: Money


class MonthView(Model):
    month: dt.date
    rows: list[MonthRow]
    unplanned: list[Unplanned]
    income: Money
    expectedIncome: Money
    spent: Money
    plannedSpending: Money
    uncategorised: int
    daysLeft: int
    canWrite: bool
    version: int  # the budget's: a change to the plan is made against it (S13.8.6)


class Flow(Model):
    name: str
    amount: Money


class CashFlow(Model):
    month: dt.date
    sources: list[Flow]
    uses: list[Flow]
    income: Money
    spending: Money


class TrendPoint(Model):
    month: dt.date
    planned: Money
    actual: Money


class RecurringRow(Model):
    payee: str
    accountId: str
    accountName: str
    every: str
    last: dt.date
    next: dt.date
    usual: Money
    lastAmount: Money
    count: int
    missed: bool
    changed: bool


def _accounts_of(s, b: Budget, viewer: str | None = None) -> list[str]:
    return budgets.account_ids(s, b, viewer)


def shape(s, b: Budget, level: str, viewer: str | None = None) -> BudgetRow:
    owner = s.get(User, b.ownerId)
    shared = len(access.holders(s, "budget", b.id, b.ownerId)) - 1 if level == "owner" else 0
    return BudgetRow(
        id=b.id,
        name=b.name,
        ownerId=b.ownerId,
        ownerName=owner.displayName,
        level=level,
        accountIds=_accounts_of(s, b, viewer),
        sharedWith=shared,
        version=b.version,
    )


def _check(s, user_id: str, body) -> list[FieldError]:
    errors = []
    if body.name is not None and (not body.name.strip() or len(body.name) > 80):
        errors.append(FieldError("name", "name-invalid", "Enter a name of up to 80 characters."))
    if body.accountIds is not None:
        mine = {a.id for a, _ in access.visible_accounts(s, user_id)}
        if any(a not in mine for a in body.accountIds):
            errors.append(
                FieldError(
                    "accountIds",
                    "account-unknown",
                    "Choose accounts you own or that are shared with you.",
                )
            )
    return errors


def _raise(errors: list[FieldError]) -> None:
    if errors:
        raise Problem(422, errors[0].code, errors[0].message, errors)


def _set_accounts(s, b: Budget, wanted: list[str], by: str) -> None:
    current = {
        m.accountId: m
        for m in s.scalars(select(BudgetAccount).where(BudgetAccount.budgetId == b.id))
    }
    now = clock.now()
    for aid in dict.fromkeys(wanted):
        m = current.get(aid)
        if m is None:
            s.add(BudgetAccount(budgetId=b.id, accountId=aid, createdAt=now))
        elif m.deleted:
            m.restore()
    for aid, m in current.items():
        if aid not in wanted and not m.deleted:
            m.mark_deleted(by, now)


def _month(value: str | None) -> dt.date:
    if not value:
        return budgets.month_of(clock.today())
    try:
        return budgets.month_of(dt.date.fromisoformat(value + "-01" if len(value) == 7 else value))
    except ValueError:
        raise Problem(422, "month-invalid", "A month such as 2026-10.") from None


@router.get("/budgets", response_model=list[BudgetRow])
def list_budgets(request: Request, c: Caller = Depends(caller)):
    with server(request).db.read() as s:
        return [shape(s, b, lvl, c.id) for b, lvl in access.visible_budgets(s, c.id)]


@router.post("/budgets", response_model=BudgetRow, status_code=201)
def create_budget(body: NewBudget, request: Request, c: Caller = Depends(caller)):
    with server(request).db.tx() as s:
        _raise(_check(s, c.id, body))
        b = Budget(id=ids.new_id("Bdgt"), ownerId=c.id, name=body.name.strip())
        s.add(b)
        s.flush()
        _set_accounts(s, b, body.accountIds, c.id)
        activity.record(
            s, "budget.created", actor=c.id, subject_kind="budget", subject_id=b.id, owner=c.id
        )
        s.flush()
        out = shape(s, b, "owner", c.id)
    return JSONResponse(
        out.model_dump(mode="json"),
        status_code=201,
        headers={"Location": f"/ui/api/budgets/{b.id}"},
    )


@router.patch("/budgets/{budget_id}", response_model=BudgetRow)
def change_budget(
    budget_id: str,
    body: BudgetChange,
    request: Request,
    c: Caller = Depends(caller),
    version: int = Depends(if_match),
):
    with server(request).db.tx() as s:
        b, lvl = access.budget(s, c.id, budget_id, "write")
        if b.version != version:
            raise stale(shape(s, b, lvl, c.id))
        _raise(_check(s, b.ownerId, body))
        fields = []
        if body.name is not None and body.name.strip() != b.name:
            b.name = body.name.strip()
            fields.append("name")
        if body.accountIds is not None:
            if lvl != "owner":
                raise Problem(403, "owner-only", "Only the owner chooses the accounts.")
            _set_accounts(s, b, body.accountIds, c.id)
            b.updatedAt = clock.now()
            fields.append("accounts")
        if fields:
            activity.record(
                s,
                "budget.updated",
                actor=c.id,
                subject_kind="budget",
                subject_id=b.id,
                owner=b.ownerId,
                detail={"fields": fields},
            )
        s.flush()
        return shape(s, b, lvl, c.id)


@router.delete("/budgets/{budget_id}", response_model=Deleted[None])
def delete_budget(
    budget_id: str, request: Request, c: Caller = Depends(caller), version: int = Depends(if_match)
):
    with server(request).db.tx() as s:
        b, lvl = access.budget(s, c.id, budget_id, "owner")
        check(b, version, lambda: shape(s, b, lvl, c.id))
        b.mark_deleted(c.id)
        activity.record(
            s, "budget.deleted", actor=c.id, subject_kind="budget", subject_id=b.id, owner=c.id
        )
        s.flush()
        return Deleted[None](deleted=gone(b))


@router.get("/budgets/{budget_id}/month", response_model=MonthView)
def budget_month(
    budget_id: str, request: Request, c: Caller = Depends(caller), month: str | None = None
):
    with server(request).db.read() as s:
        b, lvl = access.budget(s, c.id, budget_id)
        m = budgets.month_view(s, b, _month(month), clock.today(), c.id)
        return MonthView(
            month=m.month,
            rows=[MonthRow(**r.__dict__) for r in m.rows],
            unplanned=[Unplanned(categoryId=i, label=lb, spent=a) for i, lb, a in m.unplanned],
            income=m.income,
            expectedIncome=m.expectedIncome,
            spent=m.spent,
            plannedSpending=m.plannedSpending,
            uncategorised=m.uncategorised,
            daysLeft=m.daysLeft,
            canWrite=lvl in ("owner", "write"),
            version=b.version,
        )


@router.put("/budgets/{budget_id}/plan", response_model=MonthView)
def set_plan(
    budget_id: str,
    body: Plan,
    request: Request,
    c: Caller = Depends(caller),
    version: int = Depends(if_match),
):
    """From the month given on, the plan is what the body lists; earlier months keep theirs.
    The plan belongs to the budget, so it is made against the budget's version."""
    month = budgets.month_of(body.month)
    with server(request).db.tx() as s:
        b, lvl = access.budget(s, c.id, budget_id, "write")
        check(b, version, lambda: shape(s, b, lvl, c.id))
        cats = {x.id: x for x in s.scalars(select(Category).where(Category.deleted == false()))}
        errors = []
        seen = set()
        for i, ln in enumerate(body.lines):
            if ln.categoryId not in cats or cats[ln.categoryId].kind == "transfer":
                errors.append(
                    FieldError(f"lines.{i}.categoryId", "category-unknown", "Choose a category.")
                )
            elif ln.categoryId in seen:
                errors.append(
                    FieldError(f"lines.{i}.categoryId", "category-twice", "Each category once.")
                )
            seen.add(ln.categoryId)
            if ln.amount < 0:
                errors.append(
                    FieldError(f"lines.{i}.amount", "amount-negative", "Plan zero or more.")
                )
            if ln.cadence not in ("month", "year"):
                errors.append(
                    FieldError(f"lines.{i}.cadence", "cadence-invalid", "Monthly or yearly.")
                )
        _raise(errors)
        every = budgets.lines(s, b)
        current = budgets.in_force(every, month)
        wanted = {ln.categoryId: ln for ln in body.lines}
        for cat_id in set(current) | set(wanted):
            new = wanted.get(cat_id)
            values = (
                (new.amount, new.cadence, new.rollover) if new else (Decimal(0), "month", False)
            )
            old = current.get(cat_id)
            if old is not None and (old.amount, old.cadence, old.rollover) == values:
                continue
            same_month = next(
                (x for x in every if x.categoryId == cat_id and x.fromMonth == month), None
            )
            if same_month is not None:
                same_month.amount, same_month.cadence, same_month.rollover = values
            else:
                s.add(
                    BudgetLine(
                        id=ids.new_id("BdgLn"),
                        budgetId=b.id,
                        categoryId=cat_id,
                        fromMonth=month,
                        amount=values[0],
                        cadence=values[1],
                        rollover=values[2],
                    )
                )
        b.updatedAt = clock.now()
        activity.record(
            s,
            "budget.planned",
            actor=c.id,
            subject_kind="budget",
            subject_id=b.id,
            owner=b.ownerId,
        )
        s.flush()
    return budget_month(budget_id, request, c, month.isoformat()[:7])


@router.get("/budgets/{budget_id}/cash-flow", response_model=CashFlow)
def budget_cash_flow(
    budget_id: str, request: Request, c: Caller = Depends(caller), month: str | None = None
):
    with server(request).db.read() as s:
        b, _ = access.budget(s, c.id, budget_id)
        m = _month(month)
        f = budgets.cash_flow(s, b, m, c.id)
        return CashFlow(
            month=m,
            sources=[Flow(name=n, amount=a) for n, a in f["sources"]],
            uses=[Flow(name=n, amount=a) for n, a in f["uses"]],
            income=f["income"],
            spending=f["spending"],
        )


@router.get("/budgets/{budget_id}/trends", response_model=list[TrendPoint])
def budget_trends(
    budget_id: str,
    request: Request,
    c: Caller = Depends(caller),
    month: str | None = None,
    category: str | None = None,
    months: int = Query(12, ge=3, le=36),
):
    with server(request).db.read() as s:
        b, _ = access.budget(s, c.id, budget_id)
        return [
            TrendPoint(month=m, planned=p, actual=a)
            for m, p, a in budgets.trends(s, b, _month(month), category, months, c.id)
        ]


@router.get("/budgets/{budget_id}/recurring", response_model=list[RecurringRow])
def budget_recurring(budget_id: str, request: Request, c: Caller = Depends(caller)):
    """Found in the last 15 months of the budget's accounts each time it is asked."""
    with server(request).db.read() as s:
        b, _ = access.budget(s, c.id, budget_id)
        accts = budgets.account_ids(s, b, c.id)
        today = clock.today()
        txns = s.scalars(
            select(Transaction).where(
                Transaction.accountId.in_(accts),
                Transaction.deleted == false(),
                Transaction.date >= today - dt.timedelta(days=460),
            )
        ).all()
        names = {a.id: a.name for a in s.scalars(select(Account).where(Account.id.in_(accts)))}
        return [
            RecurringRow(
                payee=x.payee,
                accountId=x.accountId,
                accountName=names.get(x.accountId, ""),
                every=x.every,
                last=x.last,
                next=x.next,
                usual=x.usual,
                lastAmount=x.lastAmount,
                count=x.count,
                missed=x.missed,
                changed=x.changed,
            )
            for x in recurring.detect(txns, today)
        ]
