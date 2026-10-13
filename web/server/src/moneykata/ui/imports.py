"""Importing files into an account (requirements S1.3.1–S1.3.3): OFX/QFX, CSV with a column
mapping saved per institution, and statements (a PDF or a photo of one) read on the server and
checked before anything is saved. An import is long work: it answers 202 with a job, and the
live stream announces its end (S13.8.7)."""

import datetime as dt
import hashlib
import json
import secrets
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from decimal import Decimal

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy import false, select

from .. import access, clock, ids, receipts, settings
from ..errors import Problem, refuse
from ..importers import csvfile, ofx, statements
from ..importers.parsed import ParsedFile, ReadError, Row
from ..jobs import Job
from ..store.entities.accounts import (
    Account,
    Import,
    ImportMapping,
    StatementLayout,
    Transaction,
)
from ..store.entities.users import User
from ..store.repos import ledger as repo
from .conventions import Model, Money
from .deps import Caller, caller, server

router = APIRouter(prefix="/ui/api", tags=["imports"])
_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="mk-import")
HELD_MINUTES = 30


@dataclass
class Held:
    """An uploaded CSV waiting for its mapping to be checked (never written to disk)."""

    data: bytes
    accountId: str
    userId: str
    fileName: str
    until: dt.datetime
    # A statement: what was read and parsed, for saving and for learning its layout.
    lines: list | None = None
    statement: object | None = None
    method: str | None = None


_held: dict[str, Held] = {}
_held_lock = threading.Lock()


class JobOut(Model):
    id: str
    kind: str
    state: str
    progress: float
    result: dict | None
    error: dict | None


class ImportRow(Model):
    id: str
    format: str
    fileName: str
    coveredFrom: dt.date | None
    coveredTo: dt.date | None
    added: int
    matched: int
    changed: int
    userName: str
    createdAt: dt.datetime


class MappingIn(Model):
    mapping: dict
    save: bool = True


def job_out(job: Job) -> JobOut:
    return JobOut(
        id=job.id,
        kind=job.kind,
        state=job.state,
        progress=job.progress,
        result=job.result,
        error=job.error,
    )


def _accepted(job: Job) -> JSONResponse:
    return JSONResponse(
        job_out(job).model_dump(mode="json"),
        status_code=202,
        headers={"Location": f"/ui/api/jobs/{job.id}"},
    )


def _hold(data: bytes, account_id: str, user_id: str, name: str, **extra) -> str:
    key = "Upl_" + secrets.token_urlsafe(18)
    now = clock.now()
    with _held_lock:
        for k in [k for k, h in _held.items() if h.until < now]:
            del _held[k]
        _held[key] = Held(
            data, account_id, user_id, name, now + dt.timedelta(minutes=HELD_MINUTES), **extra
        )
    return key


def _run(
    srv,
    job: Job,
    account_id: str,
    user_id: str,
    data: bytes,
    name: str,
    mapping: dict | None,
    save_mapping: bool,
) -> None:
    srv.jobs.update(job, state="running", progress=0.1)
    try:
        if ofx.looks_like_ofx(data):
            parsed = ofx.read(data)
        else:
            if mapping is None:
                with srv.db.read() as s:
                    account = s.get(Account, account_id)
                    saved = s.scalars(
                        select(ImportMapping).where(
                            ImportMapping.ownerId == account.ownerId,
                            ImportMapping.institution == (account.institution or ""),
                            ImportMapping.deleted == false(),
                        )
                    ).first()
                if saved is None:
                    proposal = csvfile.propose(data)
                    srv.jobs.update(
                        job,
                        state="done",
                        progress=1.0,
                        result={
                            "needsMapping": True,
                            "uploadId": _hold(data, account_id, user_id, name),
                            **proposal,
                        },
                    )
                    return
                mapping = json.loads(saved.columns)
            parsed = csvfile.read(data, mapping)
        with srv.db.tx() as s:
            account, _ = access.account(s, user_id, account_id, "write")
            if mapping is not None and save_mapping and parsed.format == "csv":
                _save_mapping(s, account, mapping)
            applied = repo.apply_import(
                s, account, user_id, parsed, name, hashlib.sha256(data).hexdigest()
            )
        srv.jobs.update(
            job,
            state="done",
            progress=1.0,
            result={
                "importId": applied.importId,
                "added": applied.added,
                "matched": applied.matched,
                "changed": applied.changed,
                "transfers": applied.transfers,
                "coveredFrom": applied.coveredFrom.isoformat() if applied.coveredFrom else None,
                "coveredTo": applied.coveredTo.isoformat() if applied.coveredTo else None,
                "warnings": applied.warnings,
                "accountId": account_id,
            },
        )
        srv.events.publish("import", {"accountId": account_id}, users=[user_id])
    except (ReadError, Problem) as e:
        message = str(e) if isinstance(e, ReadError) else e.detail
        srv.jobs.update(job, state="failed", error={"code": "import-failed", "message": message})
    except Exception:
        import logging

        logging.getLogger("moneykata.imports").exception("import %s failed", job.id)
        srv.jobs.update(
            job,
            state="failed",
            error={
                "code": "import-failed",
                "message": "The import failed; an admin can find it in the log.",
            },
        )


def _save_mapping(s, account: Account, mapping: dict) -> None:
    inst = account.institution or ""
    row = s.scalars(
        select(ImportMapping).where(
            ImportMapping.ownerId == account.ownerId,
            ImportMapping.institution == inst,
            ImportMapping.deleted == false(),
        )
    ).first()
    text = json.dumps(mapping, sort_keys=True)
    if row is None:
        s.add(
            ImportMapping(
                id=ids.new_id("Map"), ownerId=account.ownerId, institution=inst, columns=text
            )
        )
    else:
        row.columns = text


@router.post("/accounts/{account_id}/imports", response_model=JobOut, status_code=202)
async def upload(
    account_id: str, request: Request, file: UploadFile = File(...), c: Caller = Depends(caller)
):
    srv = server(request)
    srv.upload_rate.check(c.id, "uploads")
    with srv.db.read() as s:
        access.account(s, c.id, account_id, "write")
        limit = settings.get(s, "importMaxMb") * 1024 * 1024
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise Problem(413, "too-large", f"Files are up to {limit // (1024 * 1024)} MB.")
    if not data:
        raise refuse("file", "file-empty", "The file is empty.")
    # The type is checked from the content, never the name (S13.7.6).
    media = receipts.sniff(data[:16])
    if media is not None:
        with srv.db.read() as s:
            if not settings.get(s, "readStatements"):
                raise Problem(
                    415,
                    "statements-off",
                    "Statements aren't read on this server: import OFX, QFX or CSV files.",
                )
        job = srv.jobs.create("import", c.id)
        _pool.submit(_run_statement, srv, job, account_id, c.id, data, file.filename or "", media)
        return _accepted(job)
    if not (ofx.looks_like_ofx(data) or csvfile.looks_like_csv(data)):
        raise Problem(
            415, "unsupported-type", "Import OFX, QFX or CSV files, or a statement (PDF or photo)."
        )
    job = srv.jobs.create("import", c.id)
    _pool.submit(_run, srv, job, account_id, c.id, data, file.filename or "file", None, False)
    return _accepted(job)


@router.post("/imports/{upload_id}/mapping", response_model=JobOut, status_code=202)
def apply_mapping(upload_id: str, body: MappingIn, request: Request, c: Caller = Depends(caller)):
    srv = server(request)
    with _held_lock:
        held = _held.get(upload_id)
    if held is None or held.userId != c.id or held.until < clock.now():
        raise Problem(404, "upload-gone", "That upload has expired; choose the file again.")
    problems = csvfile.check_mapping(body.mapping)
    if problems:
        raise refuse(f"mapping.{problems[0][0]}", "mapping-incomplete", problems[0][1])
    try:
        csvfile.read(held.data, body.mapping)
    except ReadError as e:
        raise refuse("mapping", "mapping-does-not-read", str(e)) from None
    with _held_lock:
        _held.pop(upload_id, None)
    job = srv.jobs.create("import", c.id)
    _pool.submit(
        _run, srv, job, held.accountId, c.id, held.data, held.fileName, body.mapping, body.save
    )
    return _accepted(job)


# ---------- statements (S1.3.3) ----------


def _layout(s, owner_id: str, institution: str) -> StatementLayout | None:
    return s.scalars(
        select(StatementLayout).where(
            StatementLayout.ownerId == owner_id,
            StatementLayout.institution == institution,
            StatementLayout.deleted == false(),
        )
    ).first()


def _institution_key(account: Account, st) -> str:
    return (account.institution or st.institution or "").strip()


def _run_statement(
    srv, job: Job, account_id: str, user_id: str, data: bytes, name: str, media: str
) -> None:
    """Read it in a worker process, as receipts are, then parse it with what is known of its
    institution's layout, and hold it for the person to check."""
    from ..receipts.reading import Worker

    srv.jobs.update(job, state="running", progress=0.1)
    worker = Worker()
    try:
        outcome = worker.read(data, media)
    finally:
        worker.stop()
    if outcome[0] != "ok":
        srv.jobs.update(
            job,
            state="failed",
            error={"code": "statement-unreadable", "message": f"Couldn't read it: {outcome[1]}."},
        )
        return
    _, lines, method, _engine = outcome
    with srv.db.read() as s:
        account, _ = access.account(s, user_id, account_id, "write")
        card = account.type == "credit-card"
        first = statements.parse(lines, clock.today(), None, card, account.institution)
        saved = _layout(s, account.ownerId, _institution_key(account, first))
        st = statements.parse(
            lines,
            clock.today(),
            json.loads(saved.layout) if saved else None,
            card,
            account.institution or first.institution,
        )
        existing = s.scalars(
            select(Transaction).where(
                Transaction.accountId == account_id, Transaction.deleted == false()
            )
        ).all()
    have = {(x.date, x.amount) for x in existing}
    if not st.rows:
        srv.jobs.update(
            job,
            state="failed",
            error={
                "code": "statement-empty",
                "message": "No transactions were found in it. Is it a bank or card statement?",
            },
        )
        return
    upload_id = _hold(data, account_id, user_id, name, lines=lines, statement=st, method=method)
    srv.jobs.update(
        job,
        state="done",
        progress=1.0,
        result={
            "needsReview": True,
            "uploadId": upload_id,
            "fileName": name,
            "method": method,
            "pages": None,
            "institution": st.institution,
            "learned": saved is not None,
            "periodStart": st.periodStart.isoformat() if st.periodStart else None,
            "periodEnd": st.periodEnd.isoformat() if st.periodEnd else None,
            "opening": str(st.opening) if st.opening is not None else None,
            "closing": str(st.closing) if st.closing is not None else None,
            "rows": [
                {
                    "date": r.date.isoformat(),
                    "description": r.description,
                    "amount": str(r.amount),
                    "confidence": r.confidence,
                    "present": (r.date, r.amount) in have,
                }
                for r in st.rows
            ],
            "accountId": account_id,
        },
    )


class StatementRowIn(Model):
    date: dt.date
    description: str
    amount: Money
    include: bool = True


class StatementIn(Model):
    periodStart: dt.date
    periodEnd: dt.date
    opening: Money
    closing: Money
    rows: list[StatementRowIn]
    # Save even though the transactions don't add up to the closing balance.
    acceptDifference: bool = False


@router.post("/imports/{upload_id}/statement", response_model=JobOut)
def save_statement(
    upload_id: str, body: StatementIn, request: Request, c: Caller = Depends(caller)
):
    """Nothing is saved until the person has checked it: the rows they keep become
    transactions (what is already there is matched, not added twice), the balances become the
    account's anchors, the file is kept as a receipt on the account, and the layout is learned
    for the next statement from this institution."""
    srv = server(request)
    with _held_lock:
        held = _held.get(upload_id)
    if held is None or held.userId != c.id or held.until < clock.now() or held.statement is None:
        raise Problem(404, "upload-gone", "That upload has expired; choose the file again.")
    kept = [r for r in body.rows if r.include]
    difference = body.closing - body.opening - sum((r.amount for r in kept), Decimal(0))
    if difference != 0 and not body.acceptDifference:
        raise refuse(
            "acceptDifference",
            "statement-does-not-add-up",
            f"The transactions are {abs(difference):,.2f} short of the closing balance. "
            "Correct them, or accept the difference.",
        )
    if body.periodEnd < body.periodStart:
        raise refuse("periodEnd", "period-backwards", "The period ends before it starts.")
    st = held.statement
    parsed = ParsedFile(
        format="statement",
        rows=[
            Row(
                date=r.date,
                kind="deposit" if r.amount > 0 else "withdrawal",
                amount=r.amount,
                payee=r.description.strip() or None,
            )
            for r in kept
        ],
        balances=[
            (body.periodStart - dt.timedelta(days=1), body.opening),
            (body.periodEnd, body.closing),
        ],
        coveredFrom=body.periodStart,
        coveredTo=body.periodEnd,
        institution=st.institution,
    )
    with srv.db.tx() as s:
        account, _ = access.account(s, c.id, held.accountId, "write")
        applied = repo.apply_import(
            s,
            account,
            c.id,
            parsed,
            held.fileName or "statement",
            hashlib.sha256(held.data).hexdigest(),
        )
        stored = receipts.store(s, srv, c.id, held.fileName or "statement.pdf", held.data)
        r = stored.receipt
        r.readStatus, r.readMethod, r.readAt = "read", held.method, clock.now()
        r.text = "\n".join(held.lines or [])
        r.date = body.periodEnd
        r.payee = f"{account.institution or 'Statement'} statement"
        from ..receipts import reading

        reading.index(s, r)
        receipts.attach_account(s, c.id, r, account.id)
        _learn(s, account, st, kept)
    with _held_lock:
        _held.pop(upload_id, None)
    job = srv.jobs.create("import", c.id)
    srv.jobs.update(
        job,
        state="done",
        progress=1.0,
        result={
            "importId": applied.importId,
            "added": applied.added,
            "matched": applied.matched,
            "changed": applied.changed,
            "transfers": applied.transfers,
            "coveredFrom": body.periodStart.isoformat(),
            "coveredTo": body.periodEnd.isoformat(),
            "warnings": applied.warnings,
            "accountId": held.accountId,
            "receiptId": r.id,
        },
    )
    srv.events.publish("import", {"accountId": held.accountId}, users=[c.id])
    return job_out(job)


def _learn(s, account: Account, st, kept: list[StatementRowIn]) -> None:
    by_key = {(x.date, x.description): x for x in st.rows}
    rows = [
        statements.StatementRow(
            r.date,
            r.description,
            r.amount,
            section=getattr(by_key.get((r.date, r.description)), "section", None),
        )
        for r in kept
    ]
    key = _institution_key(account, st)
    if not key:
        return
    row = _layout(s, account.ownerId, key)
    learned = statements.learn(json.loads(row.layout) if row else None, st, rows)
    text = json.dumps(learned, sort_keys=True)
    if row is None:
        s.add(
            StatementLayout(
                id=ids.new_id("Lyout"), ownerId=account.ownerId, institution=key, layout=text
            )
        )
    elif row.layout != text:
        row.layout = text


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: str, request: Request, c: Caller = Depends(caller)):
    job = server(request).jobs.get(job_id, c.id)
    if job is None:
        raise Problem(404, "not-found", "Not found")
    return job_out(job)


@router.get("/accounts/{account_id}/imports", response_model=list[ImportRow])
def list_imports(account_id: str, request: Request, c: Caller = Depends(caller)):
    with server(request).db.read() as s:
        a, _ = access.account(s, c.id, account_id)
        names = {u.id: u.displayName for u in s.scalars(select(User))}
        rows = s.scalars(
            select(Import)
            .where(Import.accountId == a.id, Import.deleted == false())
            .order_by(Import.createdAt.desc())
        ).all()
        return [
            ImportRow(
                id=i.id,
                format=i.format,
                fileName=i.fileName,
                coveredFrom=i.coveredFrom,
                coveredTo=i.coveredTo,
                added=i.added,
                matched=i.matched,
                changed=i.changed,
                userName=names.get(i.userId, ""),
                createdAt=i.createdAt,
            )
            for i in rows
        ]
