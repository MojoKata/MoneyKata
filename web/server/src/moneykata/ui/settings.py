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
    srv = server(request)
    with srv.db.tx() as s:
        # Sign-up sends links by email: it needs SMTP and the public URL (S10.1.4).
        after = {
            k: clean.get(k, settings.get(s, k)) for k in ("signupEnabled", "smtpHost", "publicUrl")
        }
        missing = [k for k in ("smtpHost", "publicUrl") if not after[k]]
        if after["signupEnabled"] and missing and not srv.config.dev:
            field = "signupEnabled" if "signupEnabled" in clean else missing[0]
            message = "Sign-up sends links by email: set up SMTP and the public URL first."
            raise Problem(
                422,
                "signup-needs-email",
                message,
                [FieldError(field, "signup-needs-email", message)],
            )
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
        out = view(s)
    if "smtpHost" in changed:
        from .prices import apply_egress

        apply_egress(srv)
    return out


# ---------- Email (S16.2) ----------


class SecretSet(Model):
    """A stored secret as the UI shows it: set, when and by whom."""

    setAt: dt.datetime
    setBy: str | None


class EmailView(Model):
    password: SecretSet | None
    waiting: int
    setAside: int
    lastRun: dt.datetime | None
    lastError: str | None


class EmailPassword(Model):
    password: str | None


class TestEmail(Model):
    to: str


def _email_view(srv, s) -> EmailView:
    from ..mail import SMTP_SECRET
    from ..store.entities.core import TaskRun
    from ..store.entities.users import User
    from ..store.repos import secrets as secret_repo

    info = secret_repo.info(s, *SMTP_SECRET)
    by = s.get(User, info.setById) if info and info.setById else None
    run = s.get(TaskRun, "mail")
    outbox = srv.config.outbox_dir
    return EmailView(
        password=SecretSet(setAt=info.setAt, setBy=by.displayName if by else None)
        if info
        else None,
        waiting=len(srv.services.mailer.waiting()),
        setAside=len(list(outbox.glob("*.refused"))) if outbox.is_dir() else 0,
        lastRun=run.finishedAt if run else None,
        lastError=run.error if run else None,
    )


@router.get("/settings/email", response_model=EmailView)
def email_status(request: Request, c: Caller = Depends(admin)):
    srv = server(request)
    with srv.db.read() as s:
        return _email_view(srv, s)


@router.put("/settings/email/password", response_model=EmailView)
def email_password(body: EmailPassword, request: Request, c: Caller = Depends(admin)):
    """The SMTP password is a secret (S14.4): set or removed, never read back."""
    from ..mail import SMTP_SECRET
    from ..store.repos import secrets as secret_repo

    srv = server(request)
    with srv.db.tx() as s:
        if body.password:
            secret_repo.put(s, srv.keys.secrets, *SMTP_SECRET, body.password, c.id)
        else:
            secret_repo.remove(s, *SMTP_SECRET)
        activity.record(
            s,
            "settings.changed",
            actor=c.id,
            for_admins=True,
            detail={"fields": ["smtpPassword"]},
        )
        s.flush()
        return _email_view(srv, s)


@router.post("/settings/email/test", response_model=TestEmail)
def email_test(request: Request, c: Caller = Depends(admin)):
    """Send a test email to the admin now, through the saved settings, and say what failed."""
    from ..mail import Email, deliver, describe, smtp_settings

    srv = server(request)
    if not c.user.email:
        raise Problem(409, "no-email", "Your profile has no email address to send to.")
    with srv.db.read() as s:
        smtp = smtp_settings(s, srv.keys.secrets)
        name = settings.get(s, "serverName")
    if smtp is None:
        raise Problem(
            422,
            "smtp-not-set",
            "Save the SMTP host first.",
            [FieldError("smtpHost", "smtp-not-set", "Save the SMTP host first.")],
        )
    from email.message import EmailMessage
    from email.utils import format_datetime, make_msgid

    note = Email(
        c.user.email,
        "MoneyKata test email",
        f"This is a test email from {name}. Email from MoneyKata reaches you.\n",
    )
    msg = EmailMessage()
    msg["From"] = smtp.sender
    msg["To"] = note.to
    msg["Subject"] = note.subject
    msg["Date"] = format_datetime(clock.now())
    msg["Message-ID"] = make_msgid(domain="moneykata.local")
    msg.set_content(note.body)
    try:
        deliver(smtp, msg, srv.guard)
    except Exception as e:
        raise Problem(502, "smtp-failed", f"The test email was not sent: {describe(e)}.") from None
    return TestEmail(to=c.user.email)


# ---------- Receipts (S16.10, S9.8.7) ----------


class ReadingQueue(Model):
    waiting: int
    reading: int
    failed: int
    read: int
    lastRun: dt.datetime | None


def _queue(s, srv) -> ReadingQueue:
    counts = dict(
        s.execute(
            text(
                'SELECT "readStatus", count(*) FROM "Receipt" WHERE NOT deleted '
                'GROUP BY "readStatus"'
            )
        ).all()
    )
    last = s.execute(text('SELECT max("readAt") FROM "Receipt"')).scalar()
    return ReadingQueue(
        waiting=counts.get("waiting", 0),
        reading=counts.get("reading", 0),
        failed=counts.get("failed", 0),
        read=counts.get("read", 0),
        lastRun=dt.datetime.fromisoformat(last).replace(tzinfo=dt.UTC)
        if isinstance(last, str)
        else last,
    )


@router.get("/settings/receipts", response_model=ReadingQueue)
def receipts_queue(request: Request, c: Caller = Depends(admin)):
    srv = server(request)
    with srv.db.read() as s:
        return _queue(s, srv)


@router.post("/settings/receipts/reread", response_model=ReadingQueue)
def reread_all(request: Request, c: Caller = Depends(admin)):
    """After a model update: every receipt read again; only empty or suggested fields are
    replaced (S9.8.6)."""
    from ..store.entities.receipts import Receipt

    srv = server(request)
    with srv.db.tx() as s:
        if not settings.get(s, "readReceipts"):
            raise Problem(409, "reading-off", "Turn on Read receipts first.")
        ids = []
        for r in s.query(Receipt).filter(Receipt.deleted.is_(False)):
            r.readStatus, r.readError = "waiting", None
            ids.append(r.id)
        activity.record(s, "receipts.reread", actor=c.id, for_admins=True)
        s.flush()
        out = _queue(s, srv)
    if srv.reader is not None:
        for rid in ids:
            srv.reader.queue(rid)
    return out


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
