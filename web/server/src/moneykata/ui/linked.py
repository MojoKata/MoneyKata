"""Linked households for the people they share with (requirements S12.10, S11.9.3): which
households share something with you, and unlocking and locking a household's copy."""

import datetime as dt
import json

from fastapi import APIRouter, Depends, Request
from sqlalchemy import false, select

from .. import settings
from ..errors import Problem
from ..links import copies
from ..links.copy import CopyError
from ..store.entities.links import Link, LinkedItem
from ..store.entities.users import User
from .conventions import Model
from .deps import Caller, caller, server

router = APIRouter(prefix="/ui/api", tags=["linked"])


class Household(Model):
    linkId: str
    serverName: str | None
    name: str | None
    avatar: dict | None
    items: int  # shared with you
    syncedAt: dt.datetime | None
    locked: bool


class CopyState(Model):
    household: Household
    hasKey: bool  # an admin has created the access key
    unlockedBy: str | None
    unlockedAt: dt.datetime | None
    locksInSeconds: int | None


class Unlock(Model):
    words: str


def _mine(s, user_id: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in s.scalars(select(LinkedItem)):
        if user_id in json.loads(row.viewers or "[]"):
            out[row.linkId] = out.get(row.linkId, 0) + 1
    return out


def _household(srv, link: Link, n: int) -> Household:
    return Household(
        linkId=link.id,
        serverName=link.peerName,
        name=link.householdName,
        avatar=json.loads(link.householdAvatar) if link.householdAvatar else None,
        items=n,
        syncedAt=link.lastOkAt,
        locked=srv.copies.get(link.id, for_person=False) is None,
    )


@router.get("/linked", response_model=list[Household])
def households(request: Request, c: Caller = Depends(caller)):
    """The households that share something with you (S12.10.1); none share nothing."""
    srv = server(request)
    with srv.db.read() as s:
        mine = _mine(s, c.id)
        rows = s.scalars(
            select(Link).where(
                Link.id.in_(list(mine)),
                Link.deleted == false(),
                Link.state.in_(("active", "paused")),
            )
        )
        return [_household(srv, link, mine[link.id]) for link in rows]


def _state(srv, s, c: Caller, link_id: str) -> CopyState:
    mine = _mine(s, c.id)
    link = s.get(Link, link_id)
    if (
        link is None
        or link.deleted
        or link.id not in mine
        or link.state not in ("active", "paused")
    ):
        raise Problem(404, "not-found", "Nothing from this household is shared with you.")
    o = srv.copies.get(link_id, for_person=False)
    who = s.get(User, o.by) if o else None
    left = srv.copies.locks_in(link_id, settings.get(s, "linkReleaseMinutes"))
    return CopyState(
        household=_household(srv, link, mine[link.id]),
        hasKey=bool(link.copyPublicKey),
        unlockedBy=who.displayName if who else None,
        unlockedAt=o.at if o else None,
        locksInSeconds=int(left) if left is not None else None,
    )


@router.get("/linked/{link_id}", response_model=CopyState)
def copy_state(link_id: str, request: Request, c: Caller = Depends(caller)):
    srv = server(request)
    with srv.db.read() as s:
        return _state(srv, s, c, link_id)


@router.post("/linked/{link_id}/unlock", response_model=CopyState)
def unlock(link_id: str, body: Unlock, request: Request, c: Caller = Depends(caller)):
    """The 12 words (S11.9.3.1): checked here, held in memory; nothing reaches the browser."""
    srv = server(request)
    with srv.db.read() as s:
        _state(srv, s, c, link_id)
    try:
        copies.unlock(srv, link_id, c.id, body.words)
    except CopyError as e:
        headers = {"Retry-After": str(int(e.wait) + 1)} if e.wait else None
        status = 429 if e.wait else 422
        raise Problem(status, e.code, e.message, headers=headers) from None
    with srv.db.read() as s:
        return _state(srv, s, c, link_id)


@router.post("/linked/{link_id}/lock", response_model=CopyState)
def lock(link_id: str, request: Request, c: Caller = Depends(caller)):
    """Lock now (S11.9.4.3): anyone the copy shares with."""
    srv = server(request)
    with srv.db.read() as s:
        _state(srv, s, c, link_id)
    copies.lock(srv, link_id, c.id, c.admin)
    with srv.db.read() as s:
        return _state(srv, s, c, link_id)
