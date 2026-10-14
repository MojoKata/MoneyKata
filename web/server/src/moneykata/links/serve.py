"""What this server sends a linked server (requirements S11.3, S11.4, S11.5): each item shared
with that server's people, worked out here as each of them would see it, with the code its own
screens use, and only what changed since the last exchange.

An item travels as its row in its list (path "") and the documents its screens read, each the
answer this server's API gives the person it names, kept by path. The receiving server shows
these and never works anything out again (S11.3.1)."""

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass, field
from types import SimpleNamespace

from sqlalchemy import delete, false, select

from .. import clock
from ..errors import Problem
from ..store.entities.links import Link, LinkSent
from ..store.entities.sharing import Share
from ..store.entities.users import User
from . import changes, keys

KINDS = ("account", "portfolio", "budget", "person", "giving-plan", "tax-book", "projection")


@dataclass
class Item:
    id: str
    kind: str
    name: str
    ownerName: str
    sharedAt: str
    viewers: set[str] = field(default_factory=set)  # the peer's user ids
    includeReceipts: bool = False


def _req(srv):
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(server=srv)))


def _dump(x):
    if isinstance(x, list):
        return [_dump(i) for i in x]
    return x.model_dump(mode="json") if hasattr(x, "model_dump") else x


def shared_items(srv, link_id: str) -> tuple[dict[str, Item], dict[str, User]]:
    """The items shared with this link's people, and those people (here, remote users)."""
    from .. import sharing
    from ..store.entities.education import Person

    with srv.db.read() as s:
        people = {
            u.id: u
            for u in s.scalars(
                select(User).where(User.linkId == link_id, User.deleted == false(), User.active)
            )
        }
        out: dict[str, Item] = {}
        if not people:
            return out, people
        for g in s.scalars(
            select(Share).where(
                Share.userId.in_(list(people)), Share.deleted == false(), Share.level == "read"
            )
        ):
            try:
                obj = sharing.item(s, g.kind, g.itemId)
            except Problem:
                continue
            if getattr(obj, "deleted", False):
                continue
            # Gifts for a person linked to a user of that server never cross (S7.8.5).
            if g.kind == "person" and isinstance(obj, Person) and obj.userId in people:
                continue
            owner = s.get(User, obj.ownerId)
            it = out.setdefault(
                g.itemId,
                Item(
                    g.itemId,
                    g.kind,
                    getattr(obj, "name", None) or str(getattr(obj, "year", "")),
                    owner.displayName if owner else "?",
                    g.createdAt.isoformat(),
                ),
            )
            it.viewers.add(people[g.userId].remoteId)
            it.includeReceipts = it.includeReceipts or g.includeReceipts
        return out, people


def _paths(srv, it: Item) -> list[tuple[str, callable]]:
    """Each document an item's screens read: its API path and how this server answers it."""
    from ..ui import accounts, budgets, gifts, giving, portfolios, projections, taxes, taxpanels
    from ..ui import transactions as txns
    from ..ui.conventions import Paging

    r, i = _req(srv), it.id
    if it.kind == "account":
        out = [
            (f"/accounts/{i}", lambda c: accounts.get_account(i, r, c)),
            (f"/accounts/{i}/series?range=All", lambda c: accounts.account_series(i, r, c, "All")),
            (f"/accounts/{i}/holdings", lambda c: accounts.account_holdings(i, r, c)),
            (
                f"/transactions?account={i}",
                lambda c: txns.list_transactions(
                    r,
                    c,
                    Paging(limit=500, after=None),
                    [i],
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    "-date",
                ),
            ),
        ]
        return out
    if it.kind == "portfolio":
        return [
            (f"/portfolios/{i}", lambda c: portfolios.get_portfolio(i, r, c)),
            (f"/portfolios/{i}/holdings", lambda c: portfolios.portfolio_holdings(i, r, c)),
            (f"/portfolios/{i}/returns", lambda c: portfolios.portfolio_returns(i, r, c)),
            (
                f"/portfolios/{i}/series?range=All",
                lambda c: portfolios.portfolio_series(i, r, c, "value", "All"),
            ),
        ]
    if it.kind == "budget":
        return [
            (f"/budgets/{i}/month", lambda c: budgets.budget_month(i, r, c, None)),
            (f"/budgets/{i}/trends", lambda c: budgets.budget_trends(i, r, c, None, None, 12)),
        ]
    if it.kind == "tax-book":
        return [
            (f"/tax-books/{i}", lambda c: taxes.get_book(i, r, c)),
            (f"/tax-books/{i}/panels", lambda c: taxpanels.get_panels(i, r, c)),
        ]
    if it.kind == "projection":
        return [(f"/projections/{i}", lambda c: projections.get_projection(i, r, c))]
    if it.kind == "giving-plan":
        year = int(it.name) if it.name.isdigit() else None
        return [(f"/giving?year={year}", lambda c: giving.get_giving(r, year, c))]
    if it.kind == "person":
        return [(f"/gifts?person={i}", lambda c: gifts.list_gifts(r, None, i, c))]
    return []


ROWS = {
    "account": "/accounts",
    "portfolio": "/portfolios",
    "budget": "/budgets",
    "tax-book": "/tax-books",
    "projection": "/projections",
    "person": "/people",
}


def _rows(srv, kind: str, c) -> dict[str, dict]:
    from ..ui import accounts, budgets, gifts, portfolios, projections, taxes

    r = _req(srv)
    fn = {
        "account": lambda: accounts.list_accounts(r, c),
        "portfolio": lambda: portfolios.list_portfolios(r, c),
        "budget": lambda: budgets.list_budgets(r, c),
        "tax-book": lambda: taxes.list_books(r, c),
        "projection": lambda: projections.list_projections(r, c),
        "person": lambda: gifts.list_people(r, c),
    }.get(kind)
    if fn is None:
        return {}
    return {row["id"]: row for row in _dump(fn()) if isinstance(row, dict) and "id" in row}


def work_out(srv, link_id: str) -> tuple[dict[str, Item], dict[tuple[str, str, str], object]]:
    """Every item and document this link's people should have, as they would see it here."""
    from ..ui.deps import Caller

    items, people = shared_items(srv, link_id)
    docs: dict[tuple[str, str, str], object] = {}
    by_viewer: dict[str, list[Item]] = defaultdict(list)
    for it in items.values():
        for v in it.viewers:
            by_viewer[v].append(it)
    remote = {u.remoteId: u for u in people.values()}
    for viewer, its in by_viewer.items():
        c = Caller(remote[viewer], None, False)
        rows: dict[str, dict[str, dict]] = {}
        for it in its:
            if it.kind not in rows:
                try:
                    rows[it.kind] = _rows(srv, it.kind, c)
                except Problem:
                    rows[it.kind] = {}
            if it.id in rows[it.kind]:
                docs[(it.id, "", viewer)] = rows[it.kind][it.id]
            for path, fn in _paths(srv, it):
                try:
                    docs[(it.id, path, viewer)] = _dump(fn(c))
                except Problem:
                    continue  # this person can't read this part: it isn't sent
    return items, docs


def _hash(body) -> str:
    return hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def change_for(srv, link_id: str, have: int, full: bool) -> dict | None:
    """The signed change that brings the peer from its `have` up to now: everything when it
    asks, or when its sequence isn't the one last sent; else only what changed. None when
    nothing has."""
    items, docs = work_out(srv, link_id)
    with srv.db.tx() as s:
        link = s.get(Link, link_id)
        full = full or have != link.sentSeq
        sent = {
            (r.itemId, r.path, r.viewer): r.hash
            for r in s.scalars(select(LinkSent).where(LinkSent.linkId == link_id))
        }
        if full:
            sent = {}
        hashes = {k: _hash(v) for k, v in docs.items()}
        sent_items = {k[0] for k in sent}
        change: dict = {"asOf": clock.now().isoformat(), "full": full}
        changed_docs = [k for k, h in hashes.items() if sent.get(k) != h]
        gone_docs = [k for k in sent if k not in hashes and k[0] in items]
        gone_items = sorted(sent_items - set(items))
        touched = {k[0] for k in changed_docs} | {k[0] for k in gone_docs}
        new_items = [i for i in items if i not in sent_items]
        item_rows = [items[i] for i in sorted(set(new_items) | touched) if i in items]
        if not full and not changed_docs and not gone_docs and not gone_items and not item_rows:
            return None
        change["items"] = [
            {
                "id": it.id,
                "kind": it.kind,
                "name": it.name,
                "ownerName": it.ownerName,
                "sharedAt": it.sharedAt,
                "viewers": sorted(it.viewers),
                "includeReceipts": it.includeReceipts,
                "version": link.sentSeq + 1,
            }
            for it in (items.values() if full else item_rows)
        ]
        change["removed"] = gone_items
        change["docs"] = [
            {"itemId": k[0], "path": k[1], "viewer": k[2], "body": docs[k]}
            for k in (docs if full else changed_docs)
        ]
        change["docsRemoved"] = [{"itemId": k[0], "path": k[1], "viewer": k[2]} for k in gone_docs]
        link.sentSeq += 1
        change["seq"] = link.sentSeq
        s.execute(delete(LinkSent).where(LinkSent.linkId == link_id))
        for (item_id, path, viewer), h in hashes.items():
            s.add(LinkSent(linkId=link_id, itemId=item_id, path=path, viewer=viewer, hash=h))
        own = keys.private_key(s, srv.keys.secrets)
    return changes.sign(own, change)
