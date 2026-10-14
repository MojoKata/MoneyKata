"""Linked households for the people they share with (requirements S12.10, S11.9.3): which
households share something with you, and unlocking and locking a household's copy."""

import datetime as dt
import json

from fastapi import APIRouter, Depends, Request
from sqlalchemy import false, select

from .. import clock, settings
from ..errors import Problem
from ..links import copies
from ..links.changes import waiting
from ..links.copy import CopyError
from ..store.entities.links import Link, LinkedItem
from ..store.entities.users import User
from .conventions import Model
from .deps import Caller, caller, server

router = APIRouter(prefix="/ui/api", tags=["linked"])


PALETTE = ("teal", "violet", "amber", "rose", "green", "blue")


class Household(Model):
    linkId: str
    colour: str  # the colour you chose for its window
    serverName: str | None
    name: str | None
    avatar: dict | None
    items: int  # shared with you
    syncedAt: dt.datetime | None
    locked: bool


class CopyState(Model):
    household: Household
    hasKey: bool  # an admin has created the access key
    waiting: int  # changes pulled while it was locked
    pulledAt: dt.datetime | None
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


def _colours(s, user_id: str, link_ids: list[str]) -> dict[str, str]:
    """Each household's colour for this user: chosen, or the next one not yet used."""
    from ..store.entities.links import LinkColour

    chosen = {
        r.linkId: r.colour
        for r in s.scalars(select(LinkColour).where(LinkColour.userId == user_id))
    }
    out, used = {}, set(chosen.values())
    for lid in sorted(link_ids):
        if lid in chosen:
            out[lid] = chosen[lid]
        else:
            out[lid] = next((c for c in PALETTE if c not in used), PALETTE[len(out) % 6])
            used.add(out[lid])
    return out


def _household(srv, link: Link, n: int, colour: str = "teal") -> Household:
    return Household(
        linkId=link.id,
        colour=colour,
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
        rows = list(rows)
        colours = _colours(s, c.id, list(mine))
        return [_household(srv, link, mine[link.id], colours[link.id]) for link in rows]


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
        household=_household(srv, link, mine[link.id], _colours(s, c.id, list(mine))[link.id]),
        hasKey=bool(link.copyPublicKey),
        waiting=len(waiting(srv.config.data_dir, link_id)),
        pulledAt=link.pulledAt,
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


class Colour(Model):
    colour: str


@router.put("/linked/{link_id}/colour", response_model=CopyState)
def set_colour(link_id: str, body: Colour, request: Request, c: Caller = Depends(caller)):
    """The colour of this household's window, for you (S12.10.3.2)."""
    from ..errors import refuse
    from ..store.entities.links import LinkColour

    if body.colour not in PALETTE:
        raise refuse("colour", "colour-invalid", "One of the palette's colours.")
    srv = server(request)
    with srv.db.tx() as s:
        _state(srv, s, c, link_id)
        row = s.get(LinkColour, (c.id, link_id))
        if row is None:
            s.add(
                LinkColour(userId=c.id, linkId=link_id, colour=body.colour, createdAt=clock.now())
            )
        else:
            row.colour = body.colour
        s.flush()
        return _state(srv, s, c, link_id)


class LinkedRow(Model):
    id: str
    kind: str
    name: str
    ownerName: str
    asOf: str
    row: dict | None  # its row in its list, as its source shows it


def _open(srv, s, c: Caller, link_id: str):
    """The unlocked copy, for a read made for this person (it counts as a use)."""
    _state(srv, s, c, link_id)
    o = srv.copies.get(link_id)
    if o is None:
        raise Problem(423, "copy-locked", "This household's copy is locked: enter its access key.")
    return o


@router.get("/linked/{link_id}/items", response_model=list[LinkedRow])
def items(link_id: str, request: Request, c: Caller = Depends(caller)):
    """What this household shares with you, each with its row (S12.10.3.4)."""
    from ..links import copydb

    srv = server(request)
    with srv.db.read() as s:
        o = _open(srv, s, c, link_id)
    out = []
    with o.engine.connect() as conn:
        rows = {
            r.itemId: json.loads(r.body)
            for r in conn.execute(
                select(copydb.Doc).where(copydb.Doc.c.path == "", copydb.Doc.c.viewer == c.id)
            )
        }
        for it in conn.execute(
            select(copydb.Item).order_by(copydb.Item.c.kind, copydb.Item.c.name)
        ):
            if c.id not in json.loads(it.viewers or "[]"):
                continue
            out.append(
                LinkedRow(
                    id=it.id,
                    kind=it.kind,
                    name=it.name,
                    ownerName=it.ownerName,
                    asOf=it.asOf,
                    row=rows.get(it.id),
                )
            )
    return out


@router.get("/linked/{link_id}/doc")
def doc(link_id: str, path: str, request: Request, c: Caller = Depends(caller)):
    """One document of an item shared with you, as its source answered it for you."""
    from ..links import copydb

    srv = server(request)
    with srv.db.read() as s:
        o = _open(srv, s, c, link_id)
    with o.engine.connect() as conn:
        body = conn.execute(
            select(copydb.Doc.c.body).where(copydb.Doc.c.path == path, copydb.Doc.c.viewer == c.id)
        ).scalar()
    if body is None:
        raise Problem(404, "not-shared", "That isn't shared with you, or hasn't arrived yet.")
    return json.loads(body)
