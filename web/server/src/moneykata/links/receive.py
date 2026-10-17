"""What this server takes from a linked server (requirements S11.3, S11.4, S11.9): a signed
change, checked, its registry kept in the main database (each item's kind, owner, when it was
shared and the people here it names, never its name or figures), and its sealed part, which
only the copy's key opens, kept in the copy's inbox as it came, with the receipts it sends,
sealed by their source."""

import datetime as dt
import json

from sqlalchemy import delete, select

from .. import activity, clock, ids
from ..store.entities.links import Link, LinkedItem
from ..store.entities.users import User
from . import changes
from .keys import unb64


def take(srv, link_id: str, change: dict, delivered: dict[str, str] | None = None) -> None:
    """Take a change from the peer. Out of sequence, the next exchange asks for everything.
    `delivered`: the receipts the peer sent with it (their ids and the names they were kept
    under); any other it names is fetched."""
    with srv.db.read() as s:
        link = s.get(Link, link_id)
        peer, got = unb64(link.peerKey), link.gotSeq
    changes.verify(peer, change)
    seq = int(change.get("seq") or 0)
    full = bool(change.get("full"))
    if not full and seq != got + 1:
        with srv.db.tx() as s:
            s.get(Link, link_id).needsFull = True
        return
    names = dict(delivered or {})
    missing = [f for f in change.get("fetch") or [] if f not in names]
    names |= fetch_files(srv, link_id, missing)
    with srv.db.tx() as s:
        link = s.get(Link, link_id)
        local = set(s.scalars(select(User.id).where(User.linkId.is_(None))))
        if full:
            s.execute(delete(LinkedItem).where(LinkedItem.linkId == link_id))
        for rid in change.get("removed") or []:
            s.execute(
                delete(LinkedItem).where(LinkedItem.linkId == link_id, LinkedItem.remoteId == rid)
            )
        now = clock.now()
        for it in change.get("items") or []:
            s.execute(
                delete(LinkedItem).where(
                    LinkedItem.linkId == link_id, LinkedItem.remoteId == it["id"]
                )
            )
            try:
                shared = dt.datetime.fromisoformat(it.get("sharedAt") or "")
            except ValueError:
                shared = now
            s.add(
                LinkedItem(
                    id=ids.new_id("LItem"),
                    linkId=link_id,
                    remoteId=it["id"],
                    kind=str(it.get("kind") or "?")[:20],
                    ownerName=str(it.get("ownerName") or "?")[:120],
                    sharedAt=shared,
                    viewers=json.dumps([v for v in it.get("viewers") or [] if v in local]),
                    includeReceipts=bool(it.get("includeReceipts")),
                    createdAt=now,
                )
            )
        link.gotSeq = seq
        link.pulledAt = now
        # A large change arriving in parts (S11.7.1): how far it has come.
        progress = change.get("progress") or {}
        if progress and int(progress.get("bytes") or 0) < int(progress.get("total") or 0):
            through = progress.get("through")
            link.syncThrough = dt.date.fromisoformat(through) if through else None
            link.syncBytes = int(progress["bytes"])
            link.syncTotal = int(progress["total"])
        else:
            link.syncThrough = link.syncBytes = link.syncTotal = None
        if full:
            link.needsFull = False
        activity.record(
            s,
            "link.pulled",
            actor=None,
            subject_kind="link",
            subject_id=link_id,
            for_admins=True,
            detail={
                "count": len(change.get("items") or []) + len(change.get("removed") or []),
                "shares": shares_of(s, link_id, change, here=True),
            },
        )
    changes.enqueue(srv, link_id, change, {"fileNames": names})


def shares_of(s, link_id: str, change: dict, here: bool) -> list[str]:
    """Which shares a change carried, for Activity (S11.8): whose item, of what kind, and for
    whom, never its name (*Alice Griffin's account for Carol*). `here`: its viewers are this
    server's users (a change taken); else the peer's (a change sent)."""
    key = User.id if here else User.remoteId
    rows = s.execute(
        select(key, User.displayName).where(
            User.linkId.is_(None) if here else User.linkId == link_id
        )
    )
    names = dict(rows.all())
    out = []
    for it in (change.get("items") or [])[:20]:
        whom = ", ".join(sorted(names.get(v, "someone") for v in it.get("viewers") or []))
        kind = str(it.get("kind") or "item").replace("-", " ")
        out.append(
            f"{it.get('ownerName') or 'someone'}'s {kind}" + (f" for {whom}" if whom else "")
        )
    return out


def forget(srv, link_id: str) -> None:
    """A link ended: its copy and what the main database knew of it go (S11.4, S11.6)."""
    from sqlalchemy import delete as sql_delete

    from ..store.entities.links import LinkSent

    srv.copies.reset(srv.config.data_dir, link_id)
    with srv.db.tx() as s:
        s.execute(sql_delete(LinkedItem).where(LinkedItem.linkId == link_id))
        s.execute(sql_delete(LinkSent).where(LinkSent.linkId == link_id))
        link = s.get(Link, link_id)
        if link is not None:
            link.copyPublicKey = link.copyKeyAt = link.copyKeyById = None


def fetch_files(srv, link_id: str, file_ids: list[str]) -> dict[str, str]:
    """The receipts a change names, fetched from the source sealed to this side's copy key and
    kept as they came, under random names (S11.9.5.2, S11.9.6), each checked against the
    source's signature over the sealed bytes; what they hold is checked against the change's
    hash when they are shown. Nothing is fetched for a copy without its access key: it asks
    for everything once it has one. Returns each file's name."""
    import secrets

    from . import client, manage, sealed
    from .copy import folder

    with srv.db.read() as s:
        link = s.get(Link, link_id)
        has_key = bool(link.copyPublicKey)
        address, peer, pins = link.address, unb64(link.peerKey), manage.pins(link)
    if not file_ids or not has_key:
        return {}
    d = folder(srv.config.data_dir, link_id) / "receipts"
    d.mkdir(parents=True, exist_ok=True)
    names: dict[str, str] = {}
    for fid in file_ids:
        name = secrets.token_hex(12) + ".mkr"
        digest: list[str] = []
        stream = client.iter_file(srv, address, peer, fid, digest, pins)
        try:
            sealed.write(d / name, stream)
        except BaseException:
            (d / name).unlink(missing_ok=True)
            (d / (name + ".tmp")).unlink(missing_ok=True)
            raise
        if not digest:
            (d / name).unlink(missing_ok=True)
            raise changes.ChangeError(f"receipt {fid} came unsigned")
        names[fid] = name
    return names


def keep_delivered(srv, link_id: str, chunks) -> str:
    """A receipt the peer delivered with its change, sealed by it: kept as it came under a
    random name until the change that names it arrives."""
    import secrets

    from . import sealed
    from .copy import folder

    d = folder(srv.config.data_dir, link_id) / "receipts"
    d.mkdir(parents=True, exist_ok=True)
    name = secrets.token_hex(12) + ".mkr"
    sealed.write(d / name, chunks)
    return name
