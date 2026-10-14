"""Settings › Linked servers (requirements S11.1, S11.7): invite a server or join one with its
code, approve a request, pause, resume or end a link, and see each link's users."""

import datetime as dt
import json

from fastapi import APIRouter, Depends, Request
from sqlalchemy import false, select

from .. import settings
from ..errors import Problem, refuse
from ..links import keys, manage
from ..links.client import LinkError
from ..store.entities.links import Link
from ..store.entities.users import User
from .conventions import Model
from .deps import Caller, admin, server
from .prices import apply_egress

router = APIRouter(prefix="/ui/api", tags=["links"])


class RemoteUser(Model):
    id: str
    username: str
    displayName: str
    email: str | None


class CopyOut(Model):
    """The link's copy (S11.7): its access key, size, and whether it is unlocked."""

    keyMadeAt: dt.datetime | None
    keyMadeBy: str | None
    sizeBytes: int
    receipts: int
    items: int
    unlocked: bool
    unlockedBy: str | None
    unlockedAt: dt.datetime | None
    locksInSeconds: int | None


class LinkOut(Model):
    id: str
    state: str  # invited, requested, pending, active, paused, ended
    role: str  # inviter or joiner
    peerName: str | None
    householdName: str | None
    householdAvatar: dict | None
    address: str | None
    fingerprint: str | None  # four groups of four, to compare
    peerVersion: str | None
    codeExpiresAt: dt.datetime | None
    lastOkAt: dt.datetime | None
    lastError: str | None
    failingSince: dt.datetime | None
    createdAt: dt.datetime
    endedAt: dt.datetime | None
    users: list[RemoteUser]
    linkedCopy: CopyOut | None = None


class LinksView(Model):
    fingerprint: str  # this server's
    address: str | None  # this server's link address, as peers reach it
    links: list[LinkOut]


class Invitation(Model):
    code: str  # shown once
    link: LinkOut


class JoinIn(Model):
    code: str


def _copy(s, srv, link: Link) -> CopyOut | None:
    if link.state not in ("active", "paused"):
        return None
    from sqlalchemy import func

    from ..links import copies
    from ..store.entities.links import LinkedItem

    size, receipts = copies.size(srv, link.id)
    o = srv.copies.get(link.id, for_person=False)
    by = s.get(User, link.copyKeyById) if link.copyKeyById else None
    who = s.get(User, o.by) if o else None
    left = srv.copies.locks_in(link.id, settings.get(s, "linkReleaseMinutes"))
    return CopyOut(
        keyMadeAt=link.copyKeyAt,
        keyMadeBy=by.displayName if by else None,
        sizeBytes=size,
        receipts=receipts,
        items=s.scalar(
            select(func.count()).select_from(LinkedItem).where(LinkedItem.linkId == link.id)
        ),
        unlocked=o is not None,
        unlockedBy=who.displayName if who else None,
        unlockedAt=o.at if o else None,
        locksInSeconds=int(left) if left is not None else None,
    )


def _out(s, link: Link, srv=None) -> LinkOut:
    users = s.scalars(
        select(User)
        .where(User.linkId == link.id, User.deleted == false())
        .order_by(User.displayName)
    )
    return LinkOut(
        id=link.id,
        state=link.state,
        role=link.role,
        peerName=link.peerName,
        householdName=link.householdName,
        householdAvatar=json.loads(link.householdAvatar) if link.householdAvatar else None,
        address=link.address,
        fingerprint=keys.short(keys.fingerprint(keys.unb64(link.peerKey)))
        if link.peerKey
        else None,
        peerVersion=link.peerVersion,
        codeExpiresAt=link.codeExpiresAt if link.state == "invited" else None,
        lastOkAt=link.lastOkAt,
        lastError=link.lastError,
        failingSince=link.failingSince,
        createdAt=link.createdAt,
        endedAt=link.endedAt,
        users=[
            RemoteUser(id=u.id, username=u.username, displayName=u.displayName, email=u.email)
            for u in users
        ],
        linkedCopy=_copy(s, srv, link) if srv is not None else None,
    )


def _problem(e: LinkError) -> Problem:
    status = 404 if e.code == "not-found" else 502 if e.code == "unreachable" else 422
    return refuse("code" if e.code.startswith("code") else None, e.code, e.message, status)


@router.get("/settings/links", response_model=LinksView)
def list_links(request: Request, c: Caller = Depends(admin)):
    srv = server(request)
    with srv.db.tx() as s:
        fp = keys.fingerprint(keys.public_of(s, srv.keys.secrets))
        rows = s.scalars(
            select(Link).where(Link.deleted == false()).order_by(Link.createdAt.desc())
        ).all()
        return LinksView(
            fingerprint=keys.short(fp),
            address=manage.own_address(s),
            links=[_out(s, r, srv) for r in rows],
        )


@router.post("/settings/links/invitations", response_model=Invitation, status_code=201)
def invite(request: Request, c: Caller = Depends(admin)):
    srv = server(request)
    try:
        link, code = manage.invite(srv, c.id)
    except LinkError as e:
        raise _problem(e) from None
    with srv.db.read() as s:
        return Invitation(code=code, link=_out(s, s.get(Link, link.id), srv))


@router.post("/settings/links/join", response_model=LinkOut, status_code=201)
def join(body: JoinIn, request: Request, c: Caller = Depends(admin)):
    srv = server(request)
    try:
        c_ = manage.decode_code(body.code)
    except LinkError as e:
        raise _problem(e) from None
    # The inviting server's address is named by this admin, so it may be reached.
    hosts, named = srv.guard.snapshot()
    from urllib.parse import urlsplit

    host = (urlsplit(c_["a"]).hostname or "").lower()
    srv.guard.allow(hosts | {host}, named | {host})
    try:
        link = manage.join(srv, body.code, c.id)
    except LinkError as e:
        raise _problem(e) from None
    finally:
        apply_egress(srv)
    with srv.db.read() as s:
        return _out(s, s.get(Link, link.id), srv)


LOCAL = ("not-found", "state-invalid", "not-requested")


def _act(request: Request, c: Caller, link_id: str, fn) -> LinkOut:
    """A change here, then a call to the peer: what the peer answers is recorded on the link,
    and only this side's own refusals fail the request."""
    srv = server(request)
    try:
        fn(srv)
    except LinkError as e:
        if e.code in LOCAL:
            raise _problem(e) from None
    apply_egress(srv)
    with srv.db.read() as s:
        link = s.get(Link, link_id)
        if link is None or link.deleted:
            raise Problem(404, "not-found", "No such link.")
        return _out(s, link, srv)


@router.post("/settings/links/{link_id}/approve", response_model=LinkOut)
def approve(link_id: str, request: Request, c: Caller = Depends(admin)):
    return _act(request, c, link_id, lambda srv: manage.approve(srv, link_id, c.id))


@router.post("/settings/links/{link_id}/pause", response_model=LinkOut)
def pause(link_id: str, request: Request, c: Caller = Depends(admin)):
    return _act(request, c, link_id, lambda srv: manage.set_state(srv, link_id, c.id, "paused"))


@router.post("/settings/links/{link_id}/resume", response_model=LinkOut)
def resume(link_id: str, request: Request, c: Caller = Depends(admin)):
    return _act(request, c, link_id, lambda srv: manage.set_state(srv, link_id, c.id, "active"))


@router.post("/settings/links/{link_id}/end", response_model=LinkOut)
def end(link_id: str, request: Request, c: Caller = Depends(admin)):
    """End a link, or reject a request, or withdraw an invitation."""
    return _act(request, c, link_id, lambda srv: manage.set_state(srv, link_id, c.id, "ended"))


@router.post("/settings/links/{link_id}/pull", response_model=LinkOut)
def pull_now(link_id: str, request: Request, c: Caller = Depends(admin)):
    """An exchange now rather than at the next hour (S11.7)."""
    return _act(request, c, link_id, lambda srv: manage.exchange(srv, link_id))


class Words(Model):
    words: list[str]  # shown once


def _copy_problem(e) -> Problem:
    status = 404 if e.code == "not-found" else 409 if e.code == "key-exists" else 422
    return Problem(status, e.code, e.message)


@router.post("/settings/links/{link_id}/copy-key", response_model=Words)
def make_copy_key(link_id: str, request: Request, c: Caller = Depends(admin)):
    """Create the access key (S11.9.2.1): 12 words, shown once."""
    from ..links import copies
    from ..links.copy import CopyError

    try:
        return Words(words=copies.make_key(server(request), link_id, c.id))
    except CopyError as e:
        raise _copy_problem(e) from None


@router.post("/settings/links/{link_id}/lock", response_model=LinkOut)
def lock_copy(link_id: str, request: Request, c: Caller = Depends(admin)):
    from ..links import copies

    return _act(request, c, link_id, lambda srv: copies.lock(srv, link_id, c.id, True))


@router.post("/settings/links/{link_id}/reset-copy", response_model=LinkOut)
def reset_copy(link_id: str, request: Request, c: Caller = Depends(admin)):
    from ..links import copies

    return _act(request, c, link_id, lambda srv: copies.reset(srv, link_id, c.id))
