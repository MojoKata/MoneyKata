"""Profile › Access tokens (requirements S10.9.1): a user's own tokens for the MCP endpoint,
made with a name, what they can read and an expiry, shown once, and revoked."""

import datetime as dt
import json

from fastapi import APIRouter, Depends, Request, Response
from pydantic import Field
from sqlalchemy import false, select

from .. import access, activity, clock, tokens
from ..errors import FieldError, Problem, refuse
from ..store.entities.users import AccessToken
from .conventions import Model
from .deps import Caller, caller, server

router = APIRouter(prefix="/ui/api", tags=["tokens"])


class TokenItem(Model):
    kind: str  # account or portfolio
    id: str


class TokenItemOut(TokenItem):
    name: str


class TokenOut(Model):
    id: str
    name: str
    scope: str  # all or chosen
    items: list[TokenItemOut]
    createdAt: dt.datetime
    expiresAt: dt.datetime
    lastUsedAt: dt.datetime | None
    expired: bool


class NewToken(Model):
    name: str
    scope: str = "all"
    items: list[TokenItem] = Field(default_factory=list)
    days: int = 90


class TokenMade(Model):
    token: TokenOut
    secret: str  # shown once


def _names(s, user_id: str) -> dict[tuple[str, str], str]:
    out = {("account", a.id): a.name for a, _ in access.visible_accounts(s, user_id)}
    out |= {("portfolio", p.id): p.name for p, _ in access.visible_portfolios(s, user_id)}
    return out


def _out(t: AccessToken, names: dict) -> TokenOut:
    items = [
        TokenItemOut(kind=i["kind"], id=i["id"], name=names.get((i["kind"], i["id"]), "—"))
        for i in json.loads(t.items or "[]")
    ]
    return TokenOut(
        id=t.id,
        name=t.name,
        scope=t.scope,
        items=items,
        createdAt=t.createdAt,
        expiresAt=t.expiresAt,
        lastUsedAt=t.lastUsedAt,
        expired=t.expiresAt <= clock.now(),
    )


@router.get("/profile/tokens", response_model=list[TokenOut])
def list_tokens(request: Request, c: Caller = Depends(caller)):
    with server(request).db.read() as s:
        names = _names(s, c.id)
        rows = s.scalars(
            select(AccessToken)
            .where(AccessToken.userId == c.id, AccessToken.deleted == false())
            .order_by(AccessToken.createdAt.desc())
        )
        return [_out(t, names) for t in rows]


@router.post("/profile/tokens", response_model=TokenMade, status_code=201)
def make_token(body: NewToken, request: Request, c: Caller = Depends(caller)):
    e: list[FieldError] = []
    name = body.name.strip()
    if not 1 <= len(name) <= 60:
        e.append(FieldError("name", "name-invalid", "A name to tell it apart: up to 60 letters."))
    if body.scope not in ("all", "chosen"):
        e.append(FieldError("scope", "scope-invalid", "Everything you can see, or chosen items."))
    if body.days not in tokens.DAYS:
        e.append(FieldError("days", "days-invalid", "30 days, 90 days or a year."))
    if body.scope == "chosen" and not body.items:
        e.append(FieldError("items", "items-missing", "Choose at least one account or portfolio."))
    if e:
        raise Problem(422, e[0].code, e[0].message, e)
    with server(request).db.tx() as s:
        names = _names(s, c.id)
        items = []
        for i in body.items if body.scope == "chosen" else []:
            if (i.kind, i.id) not in names:
                raise refuse("items", "not-found", "Only accounts and portfolios you can see.")
            items.append({"kind": i.kind, "id": i.id})
        t, secret = tokens.make(s, c.id, name, body.scope, items, body.days)
        activity.record(s, "token.created", actor=c.id, owner=c.id, detail={"name": name})
        return TokenMade(token=_out(t, names), secret=secret)


@router.delete("/profile/tokens/{token_id}", status_code=204)
def revoke_token(token_id: str, request: Request, c: Caller = Depends(caller)):
    with server(request).db.tx() as s:
        t = s.get(AccessToken, token_id)
        if t is None or t.deleted or t.userId != c.id:
            raise Problem(404, "not-found", "No such token.")
        t.mark_deleted(c.id)
        activity.record(s, "token.revoked", actor=c.id, owner=c.id, detail={"name": t.name})
    return Response(status_code=204)
