"""Portfolios (requirements §8.1): named sets of accounts, owned by a user and shared like an
account. A viewer sees only the accounts in it that are shared with them, and every figure
counts only those. *All my accounts* is everyone's implicit first portfolio."""

import datetime as dt
from decimal import Decimal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response
from pydantic import Field
from sqlalchemy import false, select

from .. import access, activity, ids, valuation
from ..errors import FieldError, Problem
from ..ledger import types as atypes
from ..store.entities.accounts import Account
from ..store.entities.sharing import Portfolio, PortfolioAccount
from ..store.entities.users import User
from ..store.repos import ledger as repo
from .conventions import Model, Money, if_match, stale
from .deps import Caller, caller, server
from .sharing import counted_for

router = APIRouter(prefix="/ui/api", tags=["portfolios"])
ALL = "all"
BENCHMARKS = ("VT", "SPY", "60-40")


class PortfolioRow(Model):
    id: str
    name: str
    implicit: bool
    ownerId: str
    ownerName: str
    ownerAvatar: str | None
    level: str
    benchmark: str
    accountIds: list[str]
    value: Money
    sharedWith: int
    notes: str | None
    version: int


class NewPortfolio(Model):
    name: str
    accountIds: list[str] = Field(default_factory=list)
    benchmark: str = "VT"
    notes: str | None = None


class PortfolioChange(Model):
    name: str | None = None
    accountIds: list[str] | None = None
    benchmark: str | None = None
    notes: str | None = None


def member_ids(s, portfolio_id: str) -> list[str]:
    return list(
        s.scalars(
            select(PortfolioAccount.accountId).where(
                PortfolioAccount.portfolioId == portfolio_id, PortfolioAccount.deleted == false()
            )
        )
    )


def all_mine(s, user_id: str) -> list[Account]:
    """My own accounts, and those shared with me that I count in my totals (§13.7)."""
    counted = counted_for(s, user_id)
    return [
        a for a, lvl in access.visible_accounts(s, user_id) if lvl == "owner" or a.id in counted
    ]


def seen_accounts(s, user_id: str, p: Portfolio | None) -> list[Account]:
    """The portfolio's accounts this user can see (§8.1.1)."""
    if p is None:
        return all_mine(s, user_id)
    r = access.reach(s, user_id)
    out = []
    for aid in member_ids(s, p.id):
        a = s.get(Account, aid)
        if a is not None and access.account_level(s, user_id, a, r):
            out.append(a)
    return sorted(out, key=lambda a: a.name)


def value_of(s, accounts: list[Account], day: dt.date | None = None) -> Decimal:
    total = Decimal(0)
    for a in accounts:
        total += valuation.account_value(s, repo.load(s, a), atypes.investing(a.type), day)
    return total


def shape(s, user: User, p: Portfolio | None, level: str) -> PortfolioRow:
    seen = seen_accounts(s, user.id, p)
    if p is None:
        return PortfolioRow(
            id=ALL,
            name="All my accounts",
            implicit=True,
            ownerId=user.id,
            ownerName=user.displayName,
            ownerAvatar=user.avatar,
            level="owner",
            benchmark="VT",
            accountIds=[a.id for a in seen],
            value=value_of(s, seen),
            sharedWith=0,
            notes=None,
            version=1,
        )
    owner = s.get(User, p.ownerId)
    shared = len(access.holders(s, "portfolio", p.id, p.ownerId)) - 1 if level == "owner" else 0
    return PortfolioRow(
        id=p.id,
        name=p.name,
        implicit=False,
        ownerId=p.ownerId,
        ownerName=owner.displayName,
        ownerAvatar=owner.avatar,
        level=level,
        benchmark=p.benchmark,
        accountIds=[a.id for a in seen],
        value=value_of(s, seen),
        sharedWith=shared,
        notes=p.notes,
        version=p.version,
    )


def _check(s, user_id: str, body) -> list[FieldError]:
    errors = []
    if body.name is not None and (not body.name.strip() or len(body.name) > 80):
        errors.append(FieldError("name", "name-invalid", "Enter a name of up to 80 characters."))
    if body.benchmark is not None and body.benchmark not in BENCHMARKS:
        errors.append(FieldError("benchmark", "benchmark-invalid", "VT, SPY or a 60/40 mix."))
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


def _set_members(s, p: Portfolio, wanted: list[str], by: str) -> None:
    current = {
        m.accountId: m
        for m in s.scalars(select(PortfolioAccount).where(PortfolioAccount.portfolioId == p.id))
    }
    now = dt.datetime.now(dt.UTC)
    for aid in dict.fromkeys(wanted):
        m = current.get(aid)
        if m is None:
            s.add(PortfolioAccount(portfolioId=p.id, accountId=aid, createdAt=now))
        elif m.deleted:
            m.deleted, m.deletedAt, m.deletedById = False, None, None
    for aid, m in current.items():
        if aid not in wanted and not m.deleted:
            m.deleted, m.deletedAt, m.deletedById = True, now, by


@router.get("/portfolios", response_model=list[PortfolioRow])
def list_portfolios(request: Request, c: Caller = Depends(caller)):
    with server(request).db.read() as s:
        return [shape(s, c.user, None, "owner")] + [
            shape(s, c.user, p, lvl) for p, lvl in access.visible_portfolios(s, c.id)
        ]


@router.post("/portfolios", response_model=PortfolioRow, status_code=201)
def create_portfolio(body: NewPortfolio, request: Request, c: Caller = Depends(caller)):
    with server(request).db.tx() as s:
        _raise(_check(s, c.id, body))
        p = Portfolio(
            id=ids.new_id("Portf"),
            ownerId=c.id,
            name=body.name.strip(),
            benchmark=body.benchmark,
            notes=body.notes,
        )
        s.add(p)
        s.flush()
        _set_members(s, p, body.accountIds, c.id)
        activity.record(
            s,
            "portfolio.created",
            actor=c.id,
            subject_kind="portfolio",
            subject_id=p.id,
            owner=c.id,
        )
        s.flush()
        out = shape(s, c.user, p, "owner")
    return JSONResponse(
        out.model_dump(mode="json"),
        status_code=201,
        headers={"Location": f"/ui/api/portfolios/{p.id}"},
    )


@router.get("/portfolios/{portfolio_id}", response_model=PortfolioRow)
def get_portfolio(portfolio_id: str, request: Request, c: Caller = Depends(caller)):
    with server(request).db.read() as s:
        if portfolio_id == ALL:
            return shape(s, c.user, None, "owner")
        p, lvl = access.portfolio(s, c.id, portfolio_id)
        return shape(s, c.user, p, lvl)


@router.patch("/portfolios/{portfolio_id}", response_model=PortfolioRow)
def change_portfolio(
    portfolio_id: str,
    body: PortfolioChange,
    request: Request,
    c: Caller = Depends(caller),
    version: int = Depends(if_match),
):
    with server(request).db.tx() as s:
        p, lvl = access.portfolio(s, c.id, portfolio_id, "write")
        if p.version != version:
            raise stale(shape(s, c.user, p, lvl))
        _raise(_check(s, p.ownerId, body))
        fields = []
        for f in ("name", "benchmark", "notes"):
            value = getattr(body, f)
            if f in body.model_fields_set and value != getattr(p, f):
                setattr(p, f, value.strip() if isinstance(value, str) and f == "name" else value)
                fields.append(f)
        if body.accountIds is not None:
            if lvl != "owner":
                raise Problem(403, "owner-only", "Only the owner chooses the accounts.")
            _set_members(s, p, body.accountIds, c.id)
            p.updatedAt = dt.datetime.now(dt.UTC)
            fields.append("accounts")
        if fields:
            activity.record(
                s,
                "portfolio.updated",
                actor=c.id,
                subject_kind="portfolio",
                subject_id=p.id,
                owner=p.ownerId,
                detail={"fields": fields},
            )
        s.flush()
        return shape(s, c.user, p, lvl)


@router.delete("/portfolios/{portfolio_id}", status_code=204)
def delete_portfolio(
    portfolio_id: str,
    request: Request,
    c: Caller = Depends(caller),
    version: int = Depends(if_match),
):
    with server(request).db.tx() as s:
        p, _ = access.portfolio(s, c.id, portfolio_id, "owner")
        if p.version != version:
            raise stale({"id": p.id, "version": p.version})
        p.mark_deleted(c.id)
        activity.record(
            s,
            "portfolio.deleted",
            actor=c.id,
            subject_kind="portfolio",
            subject_id=p.id,
            owner=p.ownerId,
        )
    return Response(status_code=204)
