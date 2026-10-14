"""Making, approving, pausing and ending links (requirements S11.1, S11.6), and the directory
each side sends the other at every exchange: its active users and its household (S11.3).

A link code is `mkl1.` and base64url JSON: the inviting server's link address (`a`), its key's
fingerprint (`f`) and a one-time secret (`c`). The inviting side keeps only the secret's hash,
and the code works once, for 24 hours."""

import contextlib
import datetime as dt
import hashlib
import json
import secrets

from sqlalchemy import false, select

from .. import activity, clock, ids, settings
from ..store.entities.links import Link
from ..store.entities.users import User
from . import client, keys
from .client import LinkError

CODE_HOURS = 24


def own_address(s) -> str | None:
    return settings.get(s, "linkAddress") or settings.get(s, "publicUrl")


def household(s) -> dict:
    return {
        "serverName": settings.get(s, "serverName"),
        "name": settings.get(s, "householdName"),
        "avatar": settings.get(s, "householdAvatar"),
    }


def directory(s) -> dict:
    """What this server tells a peer about itself at every exchange (S11.3)."""
    users = s.scalars(
        select(User)
        .where(User.deleted == false(), User.active, User.linkId.is_(None))
        .order_by(User.displayName)
    )
    return {
        "household": household(s),
        "users": [
            {"id": u.id, "username": u.username, "displayName": u.displayName, "email": u.email}
            for u in users
        ],
    }


def _hash(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def encode_code(address: str, fp: str, secret: str) -> str:
    raw = json.dumps({"a": address, "f": fp, "c": secret}, separators=(",", ":")).encode()
    return "mkl1." + keys.b64(raw)


def decode_code(code: str) -> dict:
    code = "".join(code.split())
    if not code.startswith("mkl1."):
        raise LinkError("code-invalid", "That isn't a MoneyKata link code: it starts mkl1.")
    try:
        out = json.loads(keys.unb64(code[5:]))
        assert isinstance(out, dict) and {"a", "f", "c"} <= set(out)
    except (ValueError, AssertionError):
        raise LinkError("code-invalid", "The link code is damaged: copy it again whole.") from None
    return out


def invite(srv, by: str) -> tuple[Link, str]:
    """An invitation: a link waiting for the other server, and the code shown once."""
    with srv.db.tx() as s:
        address = own_address(s)
        if not address:
            raise LinkError(
                "no-address",
                "Set this server's link address (or its public URL) first, so the other server "
                "can reach it.",
            )
        own = keys.private_key(s, srv.keys.secrets, by)
        fp = keys.fingerprint(keys.raw_public(own.public_key()))
        secret = secrets.token_urlsafe(24)
        link = Link(
            id=ids.new_id("Link"),
            state="invited",
            role="inviter",
            codeHash=_hash(secret),
            codeExpiresAt=clock.now() + dt.timedelta(hours=CODE_HOURS),
            createdById=by,
        )
        s.add(link)
        activity.record(s, "link.invited", actor=by, for_admins=True)
        s.flush()
        return link, encode_code(address, fp, secret)


def join(srv, code: str, by: str) -> Link:
    """Answer an invitation: check the inviting server's key against the code, then ask it to
    link. The link waits for that server's admin to approve it."""
    c = decode_code(code)
    hi = client.hello(srv, c["a"])
    peer = keys.unb64(hi.get("key", ""))
    if keys.fingerprint(peer) != c["f"]:
        raise LinkError(
            "fingerprint-mismatch",
            "The server at that address doesn't have the key the code names: nothing was sent.",
        )
    with srv.db.tx() as s:
        address = own_address(s)
        if not address:
            raise LinkError(
                "no-address",
                "Set this server's link address (or its public URL) first, so the other server "
                "can reach it.",
            )
        if s.scalars(
            select(Link).where(
                Link.peerKey == keys.b64(peer),
                Link.deleted == false(),
                Link.state != "ended",
            )
        ).first():
            raise LinkError("already-linked", "This server already has a link with that one.")
        mine = directory(s)
    out = client.call(
        srv,
        c["a"],
        peer,
        "/link/v1/join",
        {"code": c["c"], "address": address, **mine},
    )
    with srv.db.tx() as s:
        link = Link(
            id=ids.new_id("Link"),
            state="pending",
            role="joiner",
            address=c["a"],
            peerKey=keys.b64(peer),
            peerVersion=hi.get("version"),
            peerProtocol=hi.get("protocol"),
            createdById=by,
            lastOkAt=clock.now(),
        )
        s.add(link)
        s.flush()
        apply_directory(s, link, out)
        activity.record(s, "link.requested", actor=by, for_admins=True)
        return link


def answer_join(srv, caller_key: bytes, body: dict) -> dict:
    """The inviting side: a live code turns its invitation into a request from that key."""
    code = body.get("code") or ""
    with srv.db.tx() as s:
        link = s.scalars(
            select(Link).where(
                Link.codeHash == _hash(code), Link.state == "invited", Link.deleted == false()
            )
        ).first()
        if link is None or link.codeExpiresAt <= clock.now():
            return {"error": ("code-used", "That link code was used, expired or withdrawn.")}
        if s.scalars(
            select(Link).where(
                Link.peerKey == keys.b64(caller_key),
                Link.deleted == false(),
                Link.state != "ended",
            )
        ).first():
            return {"error": ("already-linked", "These two servers are already linked.")}
        link.state = "requested"
        link.codeHash = None
        link.peerKey = keys.b64(caller_key)
        link.address = body.get("address")
        link.lastOkAt = clock.now()
        s.flush()
        apply_directory(s, link, body)
        activity.record(s, "link.request-received", actor=None, for_admins=True)
        return directory(s)


def apply_directory(s, link: Link, payload: dict) -> None:
    """The peer's household and active users, kept as remote users by their id there: added,
    updated in place, soft-deleted when gone, and restored when they return (S11.3)."""
    h = payload.get("household") or {}
    link.peerName = h.get("serverName") or link.peerName
    link.householdName = h.get("name") or link.householdName
    if h.get("avatar") is not None:
        link.householdAvatar = json.dumps(h["avatar"])
    seen = set()
    now = clock.now()
    have = {u.remoteId: u for u in s.scalars(select(User).where(User.linkId == link.id))}
    for r in payload.get("users") or []:
        rid = str(r.get("id") or "")
        if not rid or rid in seen:
            continue
        seen.add(rid)
        u = have.get(rid)
        if u is None:
            u = User(
                id=ids.new_id("User"),
                username=str(r.get("username") or rid)[:64],
                displayName=str(r.get("displayName") or r.get("username") or "?")[:120],
                email=r.get("email"),
                linkId=link.id,
                remoteId=rid,
                alertEmails="none",
            )
            s.add(u)
            continue
        u.username = str(r.get("username") or u.username)[:64]
        u.displayName = str(r.get("displayName") or u.displayName)[:120]
        u.email = r.get("email")
        u.active = True
        if u.deleted:
            u.deleted, u.deletedAt, u.deletedById = False, None, None
    for rid, u in have.items():
        if rid not in seen and not u.deleted:
            u.deleted, u.deletedAt = True, now
    s.flush()


def end_users(s, link: Link) -> None:
    now = clock.now()
    for u in s.scalars(select(User).where(User.linkId == link.id, User.deleted == false())):
        u.deleted, u.deletedAt = True, now


def _get(s, link_id: str) -> Link:
    link = s.get(Link, link_id)
    if link is None or link.deleted:
        raise LinkError("not-found", "No such link.")
    return link


def approve(srv, link_id: str, by: str) -> Link:
    with srv.db.tx() as s:
        link = _get(s, link_id)
        if link.state != "requested":
            raise LinkError("not-requested", "Only a request can be approved.")
        link.state = "active"
        link.approvedById = by
        link.approvedAt = clock.now()
        activity.record(s, "link.approved", actor=by, for_admins=True)
    with contextlib.suppress(LinkError):  # else the other side learns at its next exchange
        exchange(srv, link_id)  # tells the other side at once when it can be reached
    return link


def set_state(srv, link_id: str, by: str, state: str) -> Link:
    """Reject a request, pause, resume or end a link on this side."""
    with srv.db.tx() as s:
        link = _get(s, link_id)
        allowed = {
            "paused": ("active",),
            "active": ("paused",),
            "ended": ("invited", "requested", "pending", "active", "paused"),
        }[state]
        if link.state not in allowed:
            raise LinkError("state-invalid", f"A link that is {link.state} can't be {state}.")
        was = link.state
        link.state = state
        if state == "ended":
            link.endedAt = clock.now()
            link.codeHash = None
            end_users(s, link)
        kind = {"paused": "link.paused", "active": "link.resumed", "ended": "link.ended"}[state]
        activity.record(s, kind, actor=by, for_admins=True)
        address, peer = link.address, link.peerKey
    if state == "ended" and was in ("requested", "pending", "active", "paused") and peer:
        with contextlib.suppress(LinkError):  # else the other side learns at its next call
            client.call(srv, address, keys.unb64(peer), "/link/v1/end")
    return link


def exchange(srv, link_id: str) -> None:
    """One exchange with the peer: each side's directory for the other's (S11.3). Whichever
    side can reach the other makes it; a refusal saying the link ended there ends it here."""
    with srv.db.read() as s:
        link = _get(s, link_id)
        if link.state not in ("active", "pending"):
            return
        address, peer, mine = link.address, keys.unb64(link.peerKey), directory(s)
    try:
        out = client.call(srv, address, peer, "/link/v1/exchange", mine)
    except LinkError as e:
        if e.code == "link-requested":
            return  # the other side's admin hasn't approved it yet
        with srv.db.tx() as s:
            link = _get(s, link_id)
            if e.code == "link-ended" or e.code == "not-linked":
                if link.state != "ended":
                    link.state, link.endedAt = "ended", clock.now()
                    end_users(s, link)
                    activity.record(s, "link.ended-by-peer", actor=None, for_admins=True)
                return
            link.lastError = e.message
            link.failingSince = link.failingSince or clock.now()
        raise
    with srv.db.tx() as s:
        link = _get(s, link_id)
        if link.state == "pending" and out.get("state") == "active":
            link.state = "active"
        link.lastOkAt, link.lastError, link.failingSince = clock.now(), None, None
        link.peerVersion = out.get("version") or link.peerVersion
        apply_directory(s, link, out)


def answer_exchange(srv, link: Link, body: dict, version: str | None) -> dict:
    with srv.db.tx() as s:
        row = _get(s, link.id)
        if row.state == "pending":
            row.state = "active"  # only an approved link calls this way
        row.lastOkAt, row.lastError, row.failingSince = clock.now(), None, None
        row.peerVersion = version or row.peerVersion
        apply_directory(s, row, body)
        return {**directory(s), "state": row.state, "version": srv.version}


def answer_end(srv, link: Link) -> None:
    with srv.db.tx() as s:
        row = _get(s, link.id)
        if row.state != "ended":
            row.state, row.endedAt = "ended", clock.now()
            end_users(s, row)
            activity.record(s, "link.ended-by-peer", actor=None, for_admins=True)


def exchange_all(srv, ctx=None) -> None:
    """Every link that exchanges: active ones, and joined ones waiting for approval."""
    with srv.db.read() as s:
        wanted = list(
            s.scalars(
                select(Link.id).where(
                    Link.deleted == false(), Link.state.in_(("active", "pending"))
                )
            )
        )
    for link_id in wanted:
        if ctx is not None and ctx.stop.is_set():
            break
        with contextlib.suppress(LinkError):  # recorded on the link; alerts follow it
            exchange(srv, link_id)
