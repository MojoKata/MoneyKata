"""Budgets (requirements S7.1–S7.4): per category, the planned amount, the actual from
categorised transactions in the budget's accounts, and what remains, with the unspent or
overspent remainder rolled over to the next period where the plan says so.

A plan line holds from its month on; a change to the plan starts a new line in the month it is
made, so past months keep the plan they had. A line of 0 takes a category out of the plan.
Monthly lines compare with the month; yearly ones with the year to date.

Amounts follow the transactions' signs: spending is shown as a positive amount spent, income
as received. A transaction with splits counts through its splits. Matched transfers and
transfer categories never count (S1.7).
"""

import datetime as dt
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import false, func, select
from sqlalchemy.orm import Session

from ..store.entities.accounts import Category, Split, Transaction
from ..store.entities.budgets import Budget, BudgetAccount, BudgetLine

ZERO = Decimal(0)
WARN_AT = Decimal("0.9")


def month_of(day: dt.date) -> dt.date:
    return day.replace(day=1)


def add_months(month: dt.date, n: int) -> dt.date:
    y, m = divmod(month.month - 1 + n, 12)
    return dt.date(month.year + y, m + 1, 1)


def month_end(month: dt.date) -> dt.date:
    return add_months(month, 1) - dt.timedelta(days=1)


def account_ids(s: Session, budget: Budget, viewer: str | None = None) -> list[str]:
    """The budget's accounts, less any loan: a loan's payments are counted at the bank. For a
    receiver (`viewer`), the owner's own accounts, and one shared with the owner only if it is
    shared with them too, so a budget never passes on an account someone else shared (S7.1.1)."""
    from .. import access
    from ..loans import TYPES
    from ..store.entities.accounts import Account

    rows = s.scalars(
        select(Account)
        .join(BudgetAccount, BudgetAccount.accountId == Account.id)
        .where(
            BudgetAccount.budgetId == budget.id,
            BudgetAccount.deleted == false(),
            Account.type.not_in(TYPES),
        )
    ).all()
    if viewer is None or viewer == budget.ownerId:
        return [a.id for a in rows]
    reach = access.reach(s, viewer)
    return [
        a.id
        for a in rows
        if a.ownerId == budget.ownerId or access.account_level(s, viewer, a, reach) is not None
    ]


@dataclass
class Tree:
    """The categories, each with its parent and kind."""

    by_id: dict[str, Category]

    def top(self, cat_id: str) -> Category:
        c = self.by_id[cat_id]
        return self.by_id[c.parentId] if c.parentId and c.parentId in self.by_id else c

    def children(self, cat_id: str) -> list[str]:
        return [c.id for c in self.by_id.values() if c.parentId == cat_id]

    def label(self, cat_id: str) -> str:
        c = self.by_id[cat_id]
        if c.parentId and c.parentId in self.by_id:
            return f"{self.by_id[c.parentId].name} › {c.name}"
        return c.name


def tree(s: Session) -> Tree:
    return Tree({c.id: c for c in s.scalars(select(Category).where(Category.deleted == false()))})


def amounts(s: Session, accounts: list[str], start: dt.date, end: dt.date) -> dict[str, Decimal]:
    """The signed total per category over the accounts, between two dates inclusive."""
    if not accounts:
        return {}
    out: dict[str, Decimal] = defaultdict(lambda: ZERO)
    txns = s.scalars(
        select(Transaction).where(
            Transaction.accountId.in_(accounts),
            Transaction.deleted == false(),
            Transaction.transferId.is_(None),
            Transaction.date >= start,
            Transaction.date <= end,
        )
    ).all()
    ids = [t.id for t in txns]
    splits: dict[str, list[Split]] = defaultdict(list)
    for chunk in range(0, len(ids), 500):
        for sp in s.scalars(
            select(Split).where(
                Split.transactionId.in_(ids[chunk : chunk + 500]), Split.deleted == false()
            )
        ):
            splits[sp.transactionId].append(sp)
    for t in txns:
        parts = splits.get(t.id)
        if parts:
            for sp in parts:
                if sp.categoryId:
                    out[sp.categoryId] += sp.amount
        elif t.categoryId:
            out[t.categoryId] += t.amount
    return dict(out)


def uncategorised(s: Session, accounts: list[str], start: dt.date, end: dt.date) -> int:
    if not accounts:
        return 0
    return s.scalar(
        select(func.count())
        .select_from(Transaction)
        .where(
            Transaction.accountId.in_(accounts),
            Transaction.deleted == false(),
            Transaction.transferId.is_(None),
            Transaction.categoryId.is_(None),
            Transaction.instrumentId.is_(None),
            Transaction.date >= start,
            Transaction.date <= end,
        )
    )


def lines(s: Session, budget: Budget) -> list[BudgetLine]:
    return list(
        s.scalars(
            select(BudgetLine)
            .where(BudgetLine.budgetId == budget.id, BudgetLine.deleted == false())
            .order_by(BudgetLine.fromMonth)
        )
    )


def in_force(all_lines: list[BudgetLine], month: dt.date) -> dict[str, BudgetLine]:
    """Per category, the line that holds in a month (a line of 0 is no plan)."""
    out: dict[str, BudgetLine] = {}
    for ln in all_lines:
        if ln.fromMonth <= month:
            out[ln.categoryId] = ln
    return {k: v for k, v in out.items() if v.amount != 0}


@dataclass
class Row:
    categoryId: str
    label: str
    kind: str
    cadence: str
    rollover: bool
    planned: Decimal  # this period's plan, with what rolled over into it
    carried: Decimal  # the part of planned that rolled over
    actual: Decimal  # spent, or received for income
    remaining: Decimal
    state: str  # under, near (90% or more), over


@dataclass
class Month:
    month: dt.date
    rows: list[Row]
    unplanned: list[tuple[str, str, Decimal]]  # (categoryId, label, spent) not in the plan
    income: Decimal
    expectedIncome: Decimal
    spent: Decimal
    plannedSpending: Decimal
    uncategorised: int
    daysLeft: int


def _actual(tree_: Tree, totals: dict[str, Decimal], cat_id: str) -> Decimal:
    """What a category's plan is compared with: it and its children, spending as positive."""
    c = tree_.by_id[cat_id]
    raw = totals.get(cat_id, ZERO) + sum(
        (totals.get(k, ZERO) for k in tree_.children(cat_id)), ZERO
    )
    return -raw if c.kind == "expense" else raw


def _state(planned: Decimal, actual: Decimal) -> str:
    if planned <= 0:
        return "over" if actual > 0 else "under"
    if actual > planned:
        return "over"
    return "near" if actual >= planned * WARN_AT else "under"


def month_view(
    s: Session, budget: Budget, month: dt.date, today: dt.date, viewer: str | None = None
) -> Month:
    tr = tree(s)
    accts = account_ids(s, budget, viewer)
    every = lines(s, budget)
    now = in_force(every, month)
    totals = amounts(s, accts, month, month_end(month))
    year_start = month.replace(month=1)
    ytd = amounts(s, accts, year_start, month_end(month))
    rows: list[Row] = []
    planned_cats = set(now)
    for cat_id, ln in now.items():
        if cat_id not in tr.by_id:
            continue
        kind = tr.by_id[cat_id].kind
        if ln.cadence == "year":
            planned, carried = ln.amount, ZERO
            actual = _actual(tr, ytd, cat_id)
        else:
            carried = _carry(s, tr, accts, every, cat_id, month) if ln.rollover else ZERO
            planned = ln.amount + carried
            actual = _actual(tr, totals, cat_id)
        rows.append(
            Row(
                categoryId=cat_id,
                label=tr.label(cat_id),
                kind=kind,
                cadence=ln.cadence,
                rollover=ln.rollover,
                planned=planned,
                carried=carried,
                actual=actual,
                remaining=planned - actual,
                state=_state(planned, actual) if kind == "expense" else "under",
            )
        )
    rows.sort(key=lambda r: (r.kind != "income", r.label))
    # Spending in a category with no plan of its own, nor under a planned parent.
    covered = set(planned_cats)
    for cid in planned_cats:
        covered |= set(tr.children(cid))
    unplanned: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for cid, amt in totals.items():
        c = tr.by_id.get(cid)
        if c is None or c.kind != "expense" or cid in covered:
            continue
        unplanned[cid] -= amt
    income = sum((amt for cid, amt in totals.items() if _kind(tr, cid) == "income"), ZERO)
    spent = -sum((amt for cid, amt in totals.items() if _kind(tr, cid) == "expense"), ZERO)
    end = month_end(month)
    return Month(
        month=month,
        rows=rows,
        unplanned=sorted(
            ((cid, tr.label(cid), amt) for cid, amt in unplanned.items() if amt != 0),
            key=lambda x: -x[2],
        ),
        income=income,
        expectedIncome=sum((r.planned for r in rows if r.kind == "income"), ZERO),
        spent=spent,
        plannedSpending=sum(
            (r.planned for r in rows if r.kind == "expense" and r.cadence == "month"), ZERO
        ),
        uncategorised=uncategorised(s, accts, month, end),
        daysLeft=max(0, (end - today).days + 1) if month <= today <= end else 0,
    )


def _kind(tr: Tree, cat_id: str) -> str | None:
    c = tr.by_id.get(cat_id)
    return c.kind if c else None


def _carry(
    s: Session,
    tr: Tree,
    accts: list[str],
    every: list[BudgetLine],
    cat_id: str,
    month: dt.date,
) -> Decimal:
    """What rolls into a month: each earlier month's plan less its actual, carried on while
    the category's plan rolls over."""
    mine = [ln for ln in every if ln.categoryId == cat_id]
    if not mine:
        return ZERO
    start = mine[0].fromMonth
    if start >= month:
        return ZERO
    totals = _monthly(s, accts, start, add_months(month, -1))
    carry = ZERO
    m = start
    while m < month:
        ln = in_force(mine, m).get(cat_id)
        if ln is None or not ln.rollover or ln.cadence != "month":
            carry = ZERO
        else:
            carry = ln.amount + carry - _actual(tr, totals.get(m, {}), cat_id)
        m = add_months(m, 1)
    return carry


def _monthly(
    s: Session, accts: list[str], first: dt.date, last: dt.date
) -> dict[dt.date, dict[str, Decimal]]:
    out: dict[dt.date, dict[str, Decimal]] = {}
    m = first
    while m <= last:
        out[m] = amounts(s, accts, m, month_end(m))
        m = add_months(m, 1)
    return out


# ---------- the other tabs (S7.4) ----------


def cash_flow(s: Session, budget: Budget, month: dt.date, viewer: str | None = None) -> dict:
    """Income by category into spending by top-level category, and what was left: the
    month's Sankey."""
    tr = tree(s)
    totals = amounts(s, account_ids(s, budget, viewer), month, month_end(month))
    sources: dict[str, Decimal] = defaultdict(lambda: ZERO)
    uses: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for cid, amt in totals.items():
        c = tr.by_id.get(cid)
        if c is None:
            continue
        if c.kind == "income":
            sources[c.name] += amt
        elif c.kind == "expense":
            uses[tr.top(cid).name] -= amt
    income = sum(sources.values(), ZERO)
    spending = sum(uses.values(), ZERO)
    if income > spending:
        uses["Saved"] = income - spending
    return {
        "sources": sorted(((k, v) for k, v in sources.items() if v > 0), key=lambda x: -x[1]),
        "uses": sorted(((k, v) for k, v in uses.items() if v > 0), key=lambda x: -x[1]),
        "income": income,
        "spending": spending,
    }


def trends(
    s: Session,
    budget: Budget,
    last_month: dt.date,
    category: str | None,
    months: int = 12,
    viewer: str | None = None,
) -> list[tuple[dt.date, Decimal, Decimal]]:
    """For each of the last months: planned and actual spending, for one category (with its
    children) or every expense category."""
    tr = tree(s)
    accts = account_ids(s, budget, viewer)
    every = lines(s, budget)
    out = []
    first = add_months(last_month, -(months - 1))
    totals = _monthly(s, accts, first, last_month)
    for i in range(months):
        m = add_months(first, i)
        plan = in_force(every, m)
        if category:
            ln = plan.get(category)
            planned = ln.amount if ln and ln.cadence == "month" else ZERO
            actual = _actual(tr, totals[m], category) if category in tr.by_id else ZERO
        else:
            planned = sum(
                (
                    ln.amount
                    for cid, ln in plan.items()
                    if ln.cadence == "month" and _kind(tr, cid) == "expense"
                ),
                ZERO,
            )
            actual = -sum(
                (amt for cid, amt in totals[m].items() if _kind(tr, cid) == "expense"), ZERO
            )
        out.append((m, planned, actual))
    return out
