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
        if full:
            link.needsFull = False
        activity.record(
            s,
            "link.pulled",
            actor=None,
            for_admins=True,
            detail={"count": len(change.get("items") or []) + len(change.get("removed") or [])},
        )
    changes.enqueue(srv, link_id, change)


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
