"""What this server takes from a linked server (requirements S11.3, S11.4, S11.9): a signed
change, checked, its registry kept in the main database (each item's kind, owner, when it was
shared and the people here it names, never its name or figures), and the change itself sealed
into the copy's inbox."""

import datetime as dt
import json

from sqlalchemy import delete, select

from .. import activity, clock, ids
from ..store.entities.links import Link, LinkedItem
from ..store.entities.users import User
from . import changes
from .keys import unb64


def take(srv, link_id: str, change: dict) -> None:
    """Take a change from the peer. Out of sequence, the next exchange asks for everything."""
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
    names, types = fetch_files(srv, link_id, change)
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
            for_admins=True,
            detail={"count": len(change.get("items") or []) + len(change.get("removed") or [])},
        )
    changes.enqueue(srv, link_id, change, {"fileNames": names, "fileTypes": types})


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


def fetch_files(srv, link_id: str, change: dict) -> tuple[dict[str, str], dict[str, str]]:
    """The receipts a change names, streamed from the source and sealed straight into the copy
    under random names as they arrive (S11.9.5.2, S11.9.6), each checked against the source's
    signature and the hash the change carries, and its type found from its first bytes, never
    taken from the change (S11.9.6.5). Nothing is fetched for a copy without its access key: it
    asks for everything once it has one. Returns each file's name and its type."""
    import secrets

    from . import client, sealed
    from .copy import folder

    files = change.get("files") or []
    with srv.db.read() as s:
        link = s.get(Link, link_id)
        public = unb64(link.copyPublicKey) if link.copyPublicKey else None
        address, peer = link.address, unb64(link.peerKey)
    if not files or public is None:
        return {}, {}
    d = folder(srv.config.data_dir, link_id) / "receipts"
    d.mkdir(parents=True, exist_ok=True)
    names: dict[str, str] = {}
    types: dict[str, str] = {}
    for f in files:
        name = secrets.token_hex(12) + ".mkr"
        digest: list[str] = []
        stream = _typed(client.iter_file(srv, address, peer, f["id"], digest), types, f["id"])
        try:
            sealed.write(d / name, sealed.seal(public, sealed.RECEIPT, link_id, f["id"], stream))
        except BaseException:
            (d / name).unlink(missing_ok=True)
            (d / (name + ".tmp")).unlink(missing_ok=True)
            raise
        if not digest or digest[0] != f.get("sha256"):
            (d / name).unlink(missing_ok=True)
            raise changes.ChangeError(f"receipt {f['id']} doesn't match its hash")
        names[f["id"]] = name
    return names, types


def _typed(stream, types: dict[str, str], file_id: str):
    """The stream passed through, its type found from its first bytes as S9.4 finds a local
    receipt's: one that isn't a receipt's type is kept as unknown, and never shown."""
    from ..receipts import sniff

    head = b""
    for piece in stream:
        if len(head) < 16:
            head += piece[: 16 - len(head)]
            if len(head) >= 16:
                types[file_id] = sniff(head) or UNKNOWN
        yield piece
    types.setdefault(file_id, sniff(head) or UNKNOWN)


UNKNOWN = "application/octet-stream"
