"""Settings, for admins (requirements S16). Each section of the screen reads and writes its
own keys; secrets and the sources come with their sections' routes."""

import datetime as dt
import json
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from sqlalchemy import select, text

from .. import activity, clock, settings, timezones
from ..errors import FieldError, Problem
from ..store.entities.core import Setting
from .conventions import Model
from .deps import Caller, admin, server

router = APIRouter(prefix="/ui/api", tags=["settings"])


class SettingsView(Model):
    values: dict[str, Any]
    sections: dict[str, list[str]]
    serverZone: str
    versions: dict[str, int]


def view(s) -> SettingsView:
    values = {k: settings.get(s, k) for k in settings.DEFINITIONS}
    sections: dict[str, list[str]] = {}
    for k, d in settings.DEFINITIONS.items():
        sections.setdefault(d.section, []).append(k)
    versions = {r.key: r.version for r in s.scalars(select(Setting))}
    return SettingsView(
        values=values, sections=sections, serverZone=timezones.host_zone(), versions=versions
    )


@router.get("/settings", response_model=SettingsView)
def get_settings(request: Request, c: Caller = Depends(admin)):
    with server(request).db.read() as s:
        return view(s)


@router.patch("/settings", response_model=SettingsView)
def change_settings(body: dict[str, Any], request: Request, c: Caller = Depends(admin)):
    """Every key is checked before any is saved; a refusal names each field (R3.7)."""
    errors: list[FieldError] = []
    clean = {}
    for key, value in body.items():
        try:
            clean[key] = settings.coerce(key, value)
        except Problem as p:
            errors += p.errors
    if errors:
        raise Problem(422, errors[0].code, errors[0].message, errors)
    with server(request).db.tx() as s:
        changed = [k for k, v in clean.items() if settings.get(s, k) != v]
        for k in changed:
            settings.put(s, k, clean[k], c.id)
        if changed:
            activity.record(
                s,
                "settings.changed",
                actor=c.id,
                for_admins=True,
                detail={"fields": sorted(changed)},
            )
        s.flush()
        return view(s)


# ---------- Key storage (S16.13, S15) ----------


class PreviousKeyOut(Model):
    fingerprint: str
    path: str
    removableAfter: dt.date | None


class Confirmation(Model):
    at: dt.datetime
    fingerprint: str
    matched: bool


class KeyStorage(Model):
    keyFile: str
    fingerprint: str
    created: dt.datetime
    ageDays: int
    reminderMonths: int
    reminderDue: bool
    dataKeyCreated: dt.datetime
    previous: list[PreviousKeyOut]
    confirmations: list[Confirmation]
    databaseBytes: int
    secrets: int
    receipts: int
    reencrypting: bool


class CheckOut(Model):
    name: str
    ok: bool
    detail: str


class KeyTest(Model):
    ok: bool
    checks: list[CheckOut]


def _database_bytes(s) -> int:
    """The database's size as SQLite counts it, reading through the write-ahead log, where a
    new server's data sits until a checkpoint: the file alone can say 0.0 MB. On a keyed
    connection SQLCipher answers `page_size` itself, as text, hence the casts."""
    pages = int(s.execute(text("PRAGMA page_count")).scalar_one())
    return pages * int(s.execute(text("PRAGMA page_size")).scalar_one())


@router.get("/settings/keys", response_model=KeyStorage)
def key_storage(request: Request, c: Caller = Depends(admin)):
    """Read only: the master key is changed only on the host (S15.4.6)."""
    from sqlalchemy import func

    from ..keys import master
    from ..store.entities.core import Activity, Secret

    srv = server(request)
    ring = srv.store.keys.ring
    now = clock.now()
    with srv.db.read() as s:
        rotated = s.scalars(
            select(Activity).where(Activity.kind == "key.rotated").order_by(Activity.at.desc())
        ).first()
        keep_days = settings.get(s, "backupCopies")
        months = settings.get(s, "keyReminderMonths")
        database_bytes = _database_bytes(s)
        confirmations = [
            Confirmation(
                at=a.at,
                fingerprint=json.loads(a.detail).get("fingerprint", ""),
                matched=a.kind == "key.verified",
            )
            for a in s.scalars(
                select(Activity)
                .where(Activity.kind.in_(("key.verified", "key.verify-failed")))
                .order_by(Activity.at.desc())
                .limit(10)
            )
        ]
        secrets = s.scalar(select(func.count()).select_from(Secret))
    age = (now - ring.master_created).days
    removable = (rotated.at + dt.timedelta(days=keep_days)).date() if rotated else None
    receipts_dir = srv.config.receipts_dir
    return KeyStorage(
        keyFile=str(srv.config.key_file),
        fingerprint=master.fingerprint(srv.store.keys.master_id),
        created=ring.master_created,
        ageDays=age,
        reminderMonths=months,
        reminderDue=bool(months) and age > months * 30.4,
        dataKeyCreated=ring.data_key_created,
        previous=[
            PreviousKeyOut(fingerprint=p.fingerprint, path=str(p.path), removableAfter=removable)
            for p in srv.config.previous_keys
        ],
        confirmations=confirmations,
        databaseBytes=database_bytes,
        secrets=secrets,
        receipts=sum(1 for _ in receipts_dir.rglob("*") if _.is_file())
        if receipts_dir.is_dir()
        else 0,
        reencrypting=srv.tasks.status().get("reencrypt", {}).get("running", False),
    )


@router.post("/settings/keys/test", response_model=KeyTest)
def key_test(request: Request, c: Caller = Depends(admin)):
    """Test: the key file passes its checks, unwraps the data key, and opens the database
    and a secret."""
    from ..config import RefuseStart
    from ..keys import master
    from ..keys import secrets as sealing
    from ..store.db import WrongKey, connect
    from ..store.entities.core import Secret

    srv = server(request)
    cfg = srv.config
    checks = []
    try:
        key = master.check_key_file(cfg.key_file, cfg.data_dir, cfg.backup_dir)
        checks.append(CheckOut(name="Key file", ok=True, detail="present, 16 bytes, mode 0400"))
        data_key = master.unwrap(key, master.read_keyring(cfg.keyring_path))
        checks.append(CheckOut(name="Data key", ok=True, detail="unwrapped by the master key"))
        conn = connect(cfg.db_path, master.DataKeys.derive(data_key).sqlcipher_key)
        conn.close()
        checks.append(CheckOut(name="Database", ok=True, detail="opens with the data key"))
    except (RefuseStart, ValueError, WrongKey) as e:
        checks.append(CheckOut(name="Key storage", ok=False, detail=str(e)))
    with srv.db.read() as s:
        row = s.scalars(select(Secret)).first()
        if row is not None:
            try:
                sealing.open_sealed(
                    srv.keys.secrets,
                    sealing.Sealed(row.ciphertext, row.nonce, row.wrappedKey),
                    row.recordType,
                    row.recordId,
                    row.field,
                )
                checks.append(CheckOut(name="Secrets", ok=True, detail="a secret opens"))
            except sealing.SecretError:
                checks.append(CheckOut(name="Secrets", ok=False, detail="a secret does not open"))
    with srv.db.tx() as s:
        activity.record(s, "keys.tested", actor=c.id, for_admins=True)
    return KeyTest(ok=all(x.ok for x in checks), checks=checks)


@router.post("/settings/keys/reencrypt", status_code=202)
def key_reencrypt(request: Request, c: Caller = Depends(admin)):
    """Re-encrypt (S15.7.2): a new data key for the database and every secret."""
    srv = server(request)
    with srv.db.tx() as s:
        activity.record(s, "keys.reencrypt-started", actor=c.id, for_admins=True)
    srv.tasks.run_now("reencrypt")
    return Response(status_code=202)


# ---------- Backups (S16.12, S14.6) ----------


class BackupOut(Model):
    name: str
    made: dt.datetime
    bytes: int
    files: int
    masterKey: str


class Backups(Model):
    directory: str
    time: str
    copies: int
    backups: list[BackupOut]
    lastRun: dt.datetime | None
    lastError: str | None
    nextRun: dt.datetime | None
    running: bool


@router.get("/settings/backups", response_model=Backups)
def backups(request: Request, c: Caller = Depends(admin)):
    from ..store import maintenance

    srv = server(request)
    out = []
    for path in reversed(maintenance.backups(srv.config)):
        try:
            meta = json.loads((path / "manifest.json").read_text())
        except (OSError, ValueError):
            continue
        out.append(
            BackupOut(
                name=path.name,
                made=dt.datetime.fromisoformat(meta["made"]),
                bytes=sum(f["bytes"] for f in meta["files"].values()),
                files=len(meta["files"]),
                masterKey=meta.get("masterKey", ""),
            )
        )
    status = srv.tasks.status().get("backups", {})
    with srv.db.read() as s:
        return Backups(
            directory=str(srv.config.backup_dir),
            time=settings.get(s, "backupTime"),
            copies=settings.get(s, "backupCopies"),
            backups=out,
            lastRun=status.get("lastRun"),
            lastError=status.get("lastError"),
            nextRun=status.get("nextRun"),
            running=status.get("running", False),
        )


@router.post("/settings/backups/run", status_code=202)
def backup_now(request: Request, c: Caller = Depends(admin)):
    srv = server(request)
    if not srv.tasks.run_now("backups"):
        raise Problem(503, "not-available", "Backups can't run right now.")
    with srv.db.tx() as s:
        activity.record(s, "backups.started", actor=c.id, for_admins=True)
    return Response(status_code=202)
