"""Receipts (requirements S9.1–S9.7): upload, the list and inbox, a receipt's fields and links,
its file and thumbnail, and the transactions it may belong to."""

import datetime as dt
import json
import urllib.parse
from decimal import Decimal

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import JSONResponse, Response, StreamingResponse

from .. import activity, clock, exactjson, parsing, receipts, settings
from ..errors import Problem, refuse
from ..keys.files import FileError
from ..receipts import reading, retention
from ..store.entities.accounts import Account, Transaction
from ..store.entities.assets import Item
from ..store.entities.education import QualifiedExpense
from ..store.entities.receipts import Receipt
from ..store.entities.users import User
from .conventions import Deleted, ExactRoute, Gone, Model, Money, check, gone, if_match, stale
from .deps import Caller, caller, server

router = APIRouter(prefix="/ui/api", route_class=ExactRoute, tags=["receipts"])


class LinkOut(Model):
    """A transaction it supports, or (a statement) the account it is kept on."""

    transactionId: str | None
    accountId: str
    accountName: str
    date: dt.date | None
    amount: Money | None
    payee: str | None


class ReceiptRow(Model):
    id: str
    fileName: str
    mediaType: str
    size: int
    uploadedAt: dt.datetime
    ownerId: str
    ownerName: str
    level: str
    date: dt.date | None
    amount: Money | None
    payee: str | None
    notes: str | None
    tags: list[str]
    links: list[LinkOut]
    hasThumbnail: bool
    readStatus: str
    readError: str | None
    filled: list[str]
    keep: bool  # kept for ever, whatever its retention (S14.10.1.3)
    filePrunedAt: dt.datetime | None  # its file removed by file pruning (S14.10.5)
    version: int


class Suggested(Model):
    """A field read from the receipt, with how sure the reader was (0–100)."""

    value: str
    confidence: int


class Suggestion(Model):
    transactionId: str
    accountName: str
    date: dt.date
    amount: Money
    payee: str | None


class ReceiptDetail(ReceiptRow):
    matches: list[Suggestion]
    text: str | None
    suggested: dict[str, Suggested]
    readMethod: str | None
    readEngine: str | None
    readAt: dt.datetime | None
    kept: str  # Kept until Mar 2031, Kept while the lot is open, Kept for ever (S14.10.3)
    keptState: str  # forever, open, until, expired, pruned
    keptUntil: dt.date | None
    keptSoon: bool  # within 90 days
    keptWhy: str | None  # Groceries keeps receipts 3 years


class ReceiptChange(Model):
    date: dt.date | None = None
    amount: Money | None = None
    payee: str | None = None
    notes: str | None = None
    tags: list[str] | None = None
    keep: bool | None = None


class Attach(Model):
    transactionId: str


def _links(s, r: Receipt) -> list[LinkOut]:
    out = []
    for ln in receipts.links(s, r.id):
        if ln.kind in ("item", "expense"):
            it = s.get(Item if ln.kind == "item" else QualifiedExpense, ln.itemId)
            a = s.get(Account, it.accountId) if it is not None and not it.deleted else None
            if a is not None and not a.deleted:
                out.append(
                    LinkOut(
                        transactionId=None,
                        accountId=a.id,
                        accountName=a.name,
                        date=None,
                        amount=None,
                        payee=it.name if ln.kind == "item" else (it.description or "Expense"),
                    )
                )
            continue
        if ln.kind == "account":
            a = s.get(Account, ln.itemId)
            if a is not None and not a.deleted:
                out.append(
                    LinkOut(
                        transactionId=None,
                        accountId=a.id,
                        accountName=a.name,
                        date=None,
                        amount=None,
                        payee="Statement",
                    )
                )
            continue
        t = s.get(Transaction, ln.itemId)
        if t is None or t.deleted:
            continue
        a = s.get(Account, t.accountId)
        out.append(
            LinkOut(
                transactionId=t.id,
                accountId=a.id,
                accountName=a.name,
                date=t.date,
                amount=t.amount,
                payee=t.payee,
            )
        )
    return out


def row(s, r: Receipt, level: str) -> ReceiptRow:
    owner = s.get(User, r.ownerId)
    return ReceiptRow(
        id=r.id,
        fileName=r.fileName,
        mediaType=r.mediaType,
        size=r.size,
        uploadedAt=r.createdAt,
        ownerId=r.ownerId,
        ownerName=owner.displayName if owner else "",
        level=level,
        date=r.date,
        amount=r.amount,
        payee=r.payee,
        notes=r.notes,
        tags=receipts.tags_of(r),
        links=_links(s, r),
        hasThumbnail=r.thumbnail is not None,
        readStatus=r.readStatus,
        readError=r.readError,
        filled=json.loads(r.filled or "[]"),
        keep=r.keep,
        filePrunedAt=r.filePrunedAt,
        version=r.version,
    )


def detail(s, user_id: str, r: Receipt, level: str) -> ReceiptDetail:
    base = row(s, r, level)
    rt = retention.retention(retention.Context(s), r)
    return ReceiptDetail(
        **base.model_dump(),
        matches=[
            Suggestion(
                transactionId=m.transaction.id,
                accountName=m.account.name,
                date=m.transaction.date,
                amount=m.transaction.amount,
                payee=m.transaction.payee,
            )
            for m in receipts.matches(s, user_id, r)
        ],
        text=r.text,
        suggested={
            k: Suggested(value=v["value"], confidence=v["confidence"])
            for k, v in json.loads(r.suggested or "{}").items()
        },
        readMethod=r.readMethod,
        readEngine=r.readEngine,
        readAt=r.readAt,
        kept=rt.label if rt.state != "pruned" else f"File pruned {r.filePrunedAt:%b %-d, %Y}",
        keptState=rt.state,
        keptUntil=rt.until,
        keptSoon=rt.soon,
        keptWhy=(
            f"{rt.category} keeps "
            + ("statements" if rt.category == "Statements" else "receipts")
            + f" {rt.years} year{'s' if rt.years != 1 else ''}"
            if rt.years
            else None
        ),
    )


@router.get("/receipts", response_model=list[ReceiptRow])
def list_receipts(
    request: Request, c: Caller = Depends(caller), show: str = "all", q: str | None = None
):
    """Newest first. *inbox*: the caller's receipts attached to nothing yet. The search looks
    in what was read from each receipt (S9.8.5) as well as its fields."""
    with server(request).db.read() as s:
        rows = [row(s, r, lvl) for r, lvl in receipts.visible(s, c.id)]
        in_text = reading.search(s, q) if q else set()
    if show == "inbox":
        rows = [r for r in rows if not r.links and r.level == "owner"]
    if q:
        words = q.lower().split()
        rows = [
            r
            for r in rows
            if r.id in in_text
            or all(
                w
                in " ".join(
                    filter(
                        None,
                        [r.fileName, r.payee, r.notes, str(r.amount or ""), " ".join(r.tags)],
                    )
                ).lower()
                for w in words
            )
        ]
    return sorted(rows, key=lambda r: r.uploadedAt, reverse=True)


@router.post("/receipts", response_model=ReceiptRow, status_code=201, responses={200: {}})
async def upload(request: Request, file: UploadFile = File(...), c: Caller = Depends(caller)):
    """One file per request; a batch is many requests. The same file again gives back the
    receipt it made (200)."""
    srv = server(request)
    srv.upload_rate.check(c.id, "uploads")
    with srv.db.read() as s:
        limit = settings.get(s, "receiptMaxMb") * 1024 * 1024
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise Problem(413, "too-large", f"Receipts are up to {limit // (1024 * 1024)} MB.")
    if not data:
        raise refuse("file", "file-empty", "The file is empty.")
    with srv.db.tx() as s:
        stored = receipts.store(s, srv, c.id, file.filename or "receipt", data)
        if not stored.existing:
            activity.record(s, "receipt.uploaded", actor=c.id, owner=c.id)
        out = row(s, stored.receipt, "owner")
    if out.readStatus == "waiting" and srv.reader is not None:
        srv.reader.queue(out.id)
    return JSONResponse(
        out.model_dump(mode="json"),
        status_code=200 if stored.existing else 201,
        headers={"Location": f"/ui/api/receipts/{out.id}"},
    )


@router.get("/receipts/{receipt_id}", response_model=ReceiptDetail)
def get_receipt(receipt_id: str, request: Request, c: Caller = Depends(caller)):
    with server(request).db.read() as s:
        r, lvl = receipts.get(s, c.id, receipt_id)
        return detail(s, c.id, r, lvl)


@router.patch("/receipts/{receipt_id}", response_model=ReceiptDetail)
def change_receipt(
    receipt_id: str,
    body: ReceiptChange,
    request: Request,
    c: Caller = Depends(caller),
    version: int = Depends(if_match),
):
    """Its date, amount, payee, notes and tags: by its owner, or by anyone who can write to
    an account it is attached in."""
    with server(request).db.tx() as s:
        r, lvl = receipts.get(s, c.id, receipt_id, "write")
        if r.version != version:
            raise stale(detail(s, c.id, r, lvl))
        sent = body.model_fields_set
        if "payee" in sent and body.payee is not None and len(body.payee) > 200:
            raise refuse("payee", "payee-too-long", "At most 200 characters.")
        if "notes" in sent and body.notes is not None and len(body.notes) > 2000:
            raise refuse("notes", "notes-too-long", "At most 2,000 characters.")
        filled = set(json.loads(r.filled or "[]"))
        for f in ("date", "amount", "payee", "notes"):
            if f in sent:
                # A value a person gives is theirs: reading again won't replace it.
                filled.discard(f)
                value = getattr(body, f)
                if isinstance(value, str):
                    value = value.strip() or None
                if f == "amount" and value is not None:
                    value = abs(Decimal(value))
                setattr(r, f, value)
        r.filled = exactjson.dumps(sorted(filled))
        if "tags" in sent and body.tags is not None:
            tags = sorted({t.strip().lower() for t in body.tags if t.strip()})
            r.tags = exactjson.dumps(tags)
        if "keep" in sent and body.keep is not None:
            r.keep = body.keep
        r.updatedAt = dt.datetime.now(dt.UTC)
        s.flush()
        return detail(s, c.id, r, lvl)


@router.post("/receipts/{receipt_id}/read", response_model=ReceiptDetail)
def read_again(receipt_id: str, request: Request, c: Caller = Depends(caller)):
    """Read it again (S9.8.6): only empty or suggested fields are replaced."""
    srv = server(request)
    with srv.db.tx() as s:
        r, lvl = receipts.get(s, c.id, receipt_id, "write")
        if not settings.get(s, "readReceipts"):
            raise Problem(409, "reading-off", "Reading receipts is off in Settings › Receipts.")
        reading.read_again(s, r)
        s.flush()
        out = detail(s, c.id, r, lvl)
    if srv.reader is not None:
        srv.reader.queue(receipt_id)
    return out


@router.delete("/receipts/{receipt_id}", response_model=Deleted[None])
def delete_receipt(
    receipt_id: str, request: Request, c: Caller = Depends(caller), version: int = Depends(if_match)
):
    with server(request).db.tx() as s:
        r, lvl = receipts.get(s, c.id, receipt_id, "owner")
        check(r, version, lambda: detail(s, c.id, r, lvl))
        receipts.delete(s, c.id, r)
        activity.record(s, "receipt.deleted", actor=c.id, owner=c.id)
        s.flush()
        return Deleted[None](deleted=gone(r))


@router.post("/receipts/{receipt_id}/links", response_model=ReceiptDetail)
def attach(receipt_id: str, body: Attach, request: Request, c: Caller = Depends(caller)):
    srv = server(request)
    with srv.db.tx() as s:
        r = receipts.to_attach(s, c.id, receipt_id, "transactionId")
        receipts.attach(s, c.id, r, body.transactionId)
        t = s.get(Transaction, body.transactionId)
        activity.record(
            s,
            "receipt.attached",
            actor=c.id,
            subject_kind="account",
            subject_id=t.accountId,
            owner=s.get(Account, t.accountId).ownerId,
        )
        s.flush()
        r, lvl = receipts.get(s, c.id, receipt_id)
        out = detail(s, c.id, r, lvl)
    srv.events.publish("receipt", {"id": receipt_id}, users=[c.id])
    return out


@router.delete(
    "/receipts/{receipt_id}/links/{transaction_id}", response_model=Deleted[ReceiptDetail]
)
def detach(receipt_id: str, transaction_id: str, request: Request, c: Caller = Depends(caller)):
    """A receipt's link to a transaction: a pair with no version of its own (S13.8.6)."""
    with server(request).db.tx() as s:
        r, _ = receipts.get(s, c.id, receipt_id)
        receipts.detach(s, c.id, r, transaction_id)
        s.flush()
        lvl = receipts.level(s, c.id, r)
        if lvl is None:
            # Detached from the only thing that let the caller see it.
            raise Problem(404, "not-found", "Not found")
        return Deleted[ReceiptDetail](
            deleted=Gone(id=f"{r.id}/{transaction_id}", deletedAt=clock.now()),
            parent=detail(s, c.id, r, lvl),
        )


def _disposition(name: str) -> str:
    return "inline; filename*=UTF-8''" + urllib.parse.quote(name)


@router.get("/receipts/{receipt_id}/file", response_class=StreamingResponse)
def receipt_file(receipt_id: str, request: Request, c: Caller = Depends(caller)):
    """Streamed through decryption, never written out as plaintext. Served inline in a
    sandbox, with its checked type, so a PDF can't run script in the app (S9.4)."""
    srv = server(request)
    with srv.db.read() as s:
        r, _ = receipts.get(s, c.id, receipt_id)
    if r.filePrunedAt is not None:
        raise Problem(410, "file-pruned", f"Its file was pruned on {r.filePrunedAt:%b %-d, %Y}.")
    headers = {
        "Content-Disposition": _disposition(r.fileName),
        "Content-Security-Policy": "sandbox",
        "Cache-Control": "private, no-store",
    }
    try:
        if r.mediaType == "image/heic":
            # Decoded in the reader's worker, never here (S9.1, S9.8.4.2).
            data = parsing.as_jpeg(receipts.whole(srv, r))
            return Response(data, media_type="image/jpeg", headers=headers)
        stream = receipts.read_file(srv, r)
        first = next(stream)
    except parsing.ReadError as e:
        raise Problem(415, "receipt-unshowable", f"The photo can't be shown: {e}") from None
    except (FileError, OSError) as e:
        raise Problem(500, "receipt-unreadable", f"The receipt's file can't be read: {e}") from None

    def body():
        yield first
        yield from stream

    return StreamingResponse(
        body(), media_type=r.mediaType, headers={**headers, "Content-Length": str(r.size)}
    )


@router.get("/receipts/{receipt_id}/thumbnail", response_class=Response)
def receipt_thumbnail(receipt_id: str, request: Request, c: Caller = Depends(caller)):
    with server(request).db.read() as s:
        r, _ = receipts.get(s, c.id, receipt_id)
        thumb = r.thumbnail
    if thumb is None:
        raise Problem(404, "no-thumbnail", "This receipt has no thumbnail.")
    return Response(
        thumb,
        media_type="image/webp",
        headers={"Cache-Control": "private, max-age=86400", "Content-Security-Policy": "sandbox"},
    )


@router.get("/transactions/{transaction_id}/receipts", response_model=list[ReceiptRow])
def transaction_receipts(transaction_id: str, request: Request, c: Caller = Depends(caller)):
    from .. import access

    with server(request).db.read() as s:
        t = s.get(Transaction, transaction_id)
        if t is None or t.deleted:
            raise Problem(404, "not-found", "Not found")
        access.account(s, c.id, t.accountId)
        ids = receipts.receipts_of(s, [t.id]).get(t.id, [])
        out = []
        for rid in ids:
            r = s.get(Receipt, rid)
            out.append(row(s, r, receipts.level(s, c.id, r) or "read"))
        return out
