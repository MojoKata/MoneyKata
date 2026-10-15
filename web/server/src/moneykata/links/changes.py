"""Changes to a linked copy (requirements S11.4, S11.9.5): each signed by its source's link key,
sealed into the copy's inbox whether or not the copy is unlocked, and applied in order, in one
transaction, once it is, with every signature checked first.

A change is JSON: its sequence number at the source (`seq`), its time (`asOf`), whether it
replaces the whole copy (`full`), and what it adds or removes: `items`, `removed`, `docs`,
`docsRemoved`, `files` and `filesRemoved`. `signature` is Ed25519 over the rest, as canonical
JSON (keys sorted, no spaces)."""

import datetime as dt
import json

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from sqlalchemy import delete, select

from .. import clock, exactjson
from ..store.entities.links import Link
from . import copydb, sealed
from .copy import folder, private_key
from .keys import b64, unb64

MAX_CHANGES = 1000
MAX_BYTES = 500 * 1024 * 1024


class ChangeError(Exception):
    pass


def _canonical(change: dict) -> bytes:
    body = {k: v for k, v in change.items() if k != "signature"}
    return exactjson.dumps(body, sort_keys=True, separators=(",", ":")).encode()


def sign(key: Ed25519PrivateKey, change: dict) -> dict:
    return {**change, "signature": b64(key.sign(_canonical(change)))}


def verify(public: bytes, change: dict) -> None:
    try:
        Ed25519PublicKey.from_public_bytes(public).verify(
            unb64(change.get("signature", "")), _canonical(change)
        )
    except InvalidSignature, ValueError:
        raise ChangeError(f"change {change.get('seq')} fails its signature check") from None


def inbox(data_dir, link_id: str):
    return folder(data_dir, link_id) / "inbox"


def waiting(data_dir, link_id: str) -> list:
    d = inbox(data_dir, link_id)
    return sorted(d.glob("*.mks")) if d.exists() else []


def enqueue(srv, link_id: str, change: dict, local: dict | None = None) -> bool:
    """Seal a signed change into the inbox; apply it at once if the copy is unlocked. Returns
    False when the inbox overflowed and was discarded: the next pull asks for everything."""
    with srv.db.read() as s:
        link = s.get(Link, link_id)
        public = unb64(link.copyPublicKey) if link and link.copyPublicKey else None
    if public is None:
        return True  # no copy yet: nothing is kept until its access key is made
    d = inbox(srv.config.data_dir, link_id)
    d.mkdir(parents=True, exist_ok=True)
    have = waiting(srv.config.data_dir, link_id)
    seq = int(have[-1].stem) + 1 if have else 1
    name = f"{seq:010d}"
    # The source's signed change, whole, and what this side added: the random names its
    # receipts were written under.
    entry = {"change": change, "local": local or {}}
    raw = exactjson.dumps(entry, separators=(",", ":")).encode()
    sealed.write(d / f"{name}.mks", sealed.seal(public, sealed.CHANGE, link_id, name, [raw]))
    have = waiting(srv.config.data_dir, link_id)
    if len(have) > MAX_CHANGES or sum(p.stat().st_size for p in have) > MAX_BYTES:
        for p in have:
            p.unlink(missing_ok=True)
        with srv.db.tx() as s:
            row = s.get(Link, link_id)
            row.needsFull, row.inboxAsOf = True, None
        return False
    with srv.db.tx() as s:
        row = s.get(Link, link_id)
        row.inboxAsOf = _as_of(change) or row.inboxAsOf
    if srv.copies.get(link_id, for_person=False) is not None:
        apply(srv, link_id)
    return True


def _as_of(change: dict) -> dt.datetime | None:
    try:
        return dt.datetime.fromisoformat(change["asOf"])
    except KeyError, ValueError, TypeError:
        return None


def apply(srv, link_id: str) -> int:
    """Apply the inbox to the unlocked copy: every change opened and its signature checked,
    then all of them in one transaction; applied files are deleted. A change that fails stops
    the apply and is reported on the link."""
    o = srv.copies.get(link_id, for_person=False)
    if o is None:
        return 0
    files = waiting(srv.config.data_dir, link_id)
    if not files:
        return 0
    with srv.db.read() as s:
        peer = unb64(s.get(Link, link_id).peerKey)
    priv = private_key(bytes(o.key))
    changes = []
    try:
        for p in files:
            with open(p, "rb") as f:
                raw = b"".join(sealed.open_sealed(priv, sealed.CHANGE, link_id, p.stem, f))
            entry = exactjson.loads(raw)
            change, local = (
                (entry["change"], entry.get("local") or {}) if "change" in entry else (entry, {})
            )
            verify(peer, change)
            changes.append((change, local))
    except (sealed.SealError, ChangeError, ValueError) as e:
        with srv.db.tx() as s:
            s.get(Link, link_id).lastError = f"A pulled change can't be applied: {e}"
        raise ChangeError(str(e)) from None
    receipts_dir = folder(srv.config.data_dir, link_id) / "receipts"
    with o.engine.begin() as conn:
        for change, local in changes:
            for name in _apply_one(conn, change, local.get("fileNames") or {}):
                (receipts_dir / name).unlink(missing_ok=True)
            conn.execute(
                copydb.Applied.insert().prefix_with("OR REPLACE"),
                {"seq": int(change.get("seq") or 0), "appliedAt": clock.now().isoformat()},
            )
    for p in files:
        p.unlink(missing_ok=True)
    with srv.db.tx() as s:
        s.get(Link, link_id).inboxAsOf = None
    return len(changes)


def _apply_one(conn, c: dict, names: dict[str, str]) -> list[str]:
    """Apply one change; returns the sealed files it leaves unnamed, to delete."""
    gone: list[str] = []
    if c.get("full"):
        gone += list(conn.execute(select(copydb.File.c.fileName)).scalars())
        for t in (copydb.Doc, copydb.File, copydb.Item):
            conn.execute(delete(t))
    for item_id in c.get("removed") or []:
        conn.execute(delete(copydb.Doc).where(copydb.Doc.c.itemId == item_id))
        conn.execute(delete(copydb.File).where(copydb.File.c.itemId == item_id))
        conn.execute(delete(copydb.Item).where(copydb.Item.c.id == item_id))
    for it in c.get("items") or []:
        conn.execute(delete(copydb.Item).where(copydb.Item.c.id == it["id"]))
        conn.execute(
            copydb.Item.insert(),
            {
                "id": it["id"],
                "kind": it["kind"],
                "name": it.get("name") or "",
                "ownerName": it.get("ownerName") or "",
                "viewers": json.dumps(it.get("viewers") or []),
                "version": int(it.get("version") or 0),
                "asOf": it.get("asOf") or c.get("asOf") or "",
            },
        )
    for d in c.get("docsRemoved") or []:
        conn.execute(
            delete(copydb.Doc).where(
                copydb.Doc.c.itemId == d["itemId"],
                copydb.Doc.c.path == d["path"],
                copydb.Doc.c.viewer == d["viewer"],
            )
        )
    for d in c.get("docs") or []:
        conn.execute(
            copydb.Doc.insert().prefix_with("OR REPLACE"),
            {
                "itemId": d["itemId"],
                "path": d["path"],
                "viewer": d["viewer"],
                "body": exactjson.dumps(d["body"], separators=(",", ":")),
            },
        )
    for fid in c.get("filesRemoved") or []:
        gone += list(
            conn.execute(select(copydb.File.c.fileName).where(copydb.File.c.id == fid)).scalars()
        )
        conn.execute(delete(copydb.File).where(copydb.File.c.id == fid))
    for f in c.get("files") or []:
        if f["id"] not in names:
            continue  # not fetched (the copy had no key yet): it comes with everything later
        gone += list(
            conn.execute(
                select(copydb.File.c.fileName).where(copydb.File.c.id == f["id"])
            ).scalars()
        )
        conn.execute(
            copydb.File.insert().prefix_with("OR REPLACE"),
            {
                "id": f["id"],
                "itemId": f["itemId"],
                "fileName": names[f["id"]],
                "contentType": f.get("contentType") or "application/octet-stream",
                "length": int(f.get("length") or 0),
                "sha256": f["sha256"],
                "thumbnail": f.get("thumbnail"),
                "meta": json.dumps(f.get("meta") or {}),
            },
        )
    return [g for g in gone if g not in names.values()]


def orphans(srv, link_id: str) -> int:
    """Remove files no row names, left behind after a crash (S11.9.6.6); needs the copy open.
    Temporary files go whether or not it is."""
    base = folder(srv.config.data_dir, link_id)
    gone = 0
    for p in list(base.rglob("*.tmp")):
        p.unlink(missing_ok=True)
        gone += 1
    o = srv.copies.get(link_id, for_person=False)
    if o is None or not (base / "receipts").exists():
        return gone
    with o.engine.connect() as conn:
        named = set(conn.execute(select(copydb.File.c.fileName)).scalars())
    for p in (base / "receipts").glob("*.mkr"):
        if p.name not in named:
            p.unlink(missing_ok=True)
            gone += 1
    return gone
