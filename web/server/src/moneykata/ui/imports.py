"""Importing files into an account (requirements §4.3.1–§4.3.2): OFX/QFX, and CSV with a
column mapping saved per institution. An import is long work: it answers 202 with a job, and
the live stream announces its end (§16.8.7)."""

import datetime as dt
import hashlib
import json
import secrets
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy import false, select

from .. import access, ids, settings
from ..errors import Problem, refuse
from ..importers import csvfile, ofx
from ..importers.parsed import ReadError
from ..jobs import Job
from ..store.entities.accounts import Account, Import, ImportMapping
from ..store.entities.users import User
from ..store.repos import ledger as repo
from .conventions import Model
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


def _hold(data: bytes, account_id: str, user_id: str, name: str) -> str:
    key = "Upl_" + secrets.token_urlsafe(18)
    now = dt.datetime.now(dt.UTC)
    with _held_lock:
        for k in [k for k, h in _held.items() if h.until < now]:
            del _held[k]
        _held[key] = Held(data, account_id, user_id, name, now + dt.timedelta(minutes=HELD_MINUTES))
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
    # The type is checked from the content, never the name (§16.7.6).
    if not (ofx.looks_like_ofx(data) or csvfile.looks_like_csv(data)):
        raise Problem(415, "unsupported-type", "Import OFX, QFX or CSV files.")
    job = srv.jobs.create("import", c.id)
    _pool.submit(_run, srv, job, account_id, c.id, data, file.filename or "file", None, False)
    return _accepted(job)


@router.post("/imports/{upload_id}/mapping", response_model=JobOut, status_code=202)
def apply_mapping(upload_id: str, body: MappingIn, request: Request, c: Caller = Depends(caller)):
    srv = server(request)
    with _held_lock:
        held = _held.get(upload_id)
    if held is None or held.userId != c.id or held.until < dt.datetime.now(dt.UTC):
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
