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
from .conventions import ExactRoute, Loose, Model, check_version, if_match, version_of
from .deps import Caller, admin, server

router = APIRouter(prefix="/ui/api", route_class=ExactRoute, tags=["settings"])


class SettingsView(Model):
    values: dict[str, Any]
    sections: dict[str, list[str]]
    serverZone: str
    versions: dict[str, int]
    version: int  # all of them together: a change is made against it (S13.8.6)


def view(s) -> SettingsView:
    values = {k: settings.get(s, k) for k in settings.DEFINITIONS}
    sections: dict[str, list[str]] = {}
    for k, d in settings.DEFINITIONS.items():
        sections.setdefault(d.section, []).append(k)
    versions = {r.key: r.version for r in s.scalars(select(Setting))}
    return SettingsView(
        values=values,
        sections=sections,
        serverZone=timezones.host_zone(),
        versions=versions,
        version=version_of(s, Setting),
    )


@router.get("/settings", response_model=SettingsView)
def get_settings(request: Request, c: Caller = Depends(admin)):
    with server(request).db.read() as s:
        return view(s)


@router.patch("/settings", response_model=SettingsView)
def change_settings(
    body: Loose, request: Request, c: Caller = Depends(admin), version: int = Depends(if_match)
):
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
        check_version(version_of(s, Setting), version, lambda: view(s))
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
    if "smtpHost" in changed or any(k.startswith("bitcoin") for k in changed):
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


# ---------- Bitcoin (S16.7, S1.6.2) ----------


class BitcoinView(Model):
    password: SecretSet | None  # Bitcoin Core's RPC password
    wallets: int
    lastRun: dt.datetime | None
    lastError: str | None
    certificate: str | None  # the Electrum server's, trusted (S1.6.2.4): its SHA-256
    certificateOffered: str | None  # another one it presented since, waiting to be confirmed


class BitcoinPassword(Model):
    password: str | None


class BitcoinTest(Model):
    answer: str


def _bitcoin_view(s) -> BitcoinView:
    from sqlalchemy import false, func, select

    from ..bitcoin.sync import PASSWORD
    from ..store.entities.accounts import Account
    from ..store.entities.core import TaskRun
    from ..store.entities.users import User
    from ..store.repos import secrets as secret_repo

    info = secret_repo.info(s, *PASSWORD)
    by = s.get(User, info.setById) if info and info.setById else None
    run = s.get(TaskRun, "bitcoin")
    return BitcoinView(
        password=SecretSet(setAt=info.setAt, setBy=by.displayName if by else None)
        if info
        else None,
        wallets=s.scalar(
            select(func.count())
            .select_from(Account)
            .where(Account.type == "crypto-wallet", Account.deleted == false())
        ),
        lastRun=run.finishedAt if run else None,
        lastError=run.error if run else None,
        certificate=settings.get(s, "bitcoinNodeCert"),
        certificateOffered=settings.get(s, "bitcoinNodeCertOffered"),
    )


@router.get("/settings/bitcoin", response_model=BitcoinView)
def bitcoin_status(request: Request, c: Caller = Depends(admin)):
    with server(request).db.read() as s:
        return _bitcoin_view(s)


@router.put("/settings/bitcoin/password", response_model=BitcoinView)
def bitcoin_password(body: BitcoinPassword, request: Request, c: Caller = Depends(admin)):
    """Bitcoin Core's RPC password is a secret (S14.4): set or removed, never read back."""
    from ..bitcoin.sync import PASSWORD
    from ..store.repos import secrets as secret_repo

    srv = server(request)
    with srv.db.tx() as s:
        if body.password:
            secret_repo.put(s, srv.keys.secrets, *PASSWORD, body.password, c.id)
        else:
            secret_repo.remove(s, *PASSWORD)
        activity.record(
            s,
            "settings.changed",
            actor=c.id,
            for_admins=True,
            detail={"fields": ["bitcoinPassword"]},
        )
        s.flush()
        return _bitcoin_view(s)


class TrustCertificate(Model):
    sha256: str


@router.post("/settings/bitcoin/certificate", response_model=BitcoinView)
def bitcoin_certificate(body: TrustCertificate, request: Request, c: Caller = Depends(admin)):
    """An admin confirms the Electrum server's certificate, as Test showed it: it is then the
    one trusted, and any other refused (S1.6.2.4)."""
    import re

    sha = body.sha256.strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", sha):
        from ..errors import refuse

        raise refuse("sha256", "fingerprint-invalid", "The SHA-256 fingerprint Test showed.")
    with server(request).db.tx() as s:
        settings.put(s, "bitcoinNodeCert", sha, c.id)
        settings.put(s, "bitcoinNodeCertOffered", None, c.id)
        activity.record(
            s,
            "settings.changed",
            actor=c.id,
            for_admins=True,
            detail={"fields": ["bitcoinNodeCert"]},
        )
        s.flush()
        return _bitcoin_view(s)


@router.post("/settings/bitcoin/test", response_model=BitcoinTest)
def bitcoin_test(request: Request, c: Caller = Depends(admin)):
    """Ask the saved explorer or node for the chain's height, and say what failed."""
    from ..bitcoin import sync
    from ..bitcoin.sources import SourceError

    srv = server(request)
    with srv.db.read() as s:
        cfg = sync.config(s, srv.keys.secrets)
        src = sync.source(srv, s)
    hosts, named = cfg.hosts()
    if hosts and not srv.config.stubs:
        # The host is allowed for this test even before a wallet needs it.
        current_hosts, current_named = srv.guard.snapshot()
        srv.guard.allow(current_hosts | set(hosts), current_named | set(named))
    from .prices import apply_egress

    try:
        return BitcoinTest(answer=src.test())
    except SourceError as e:
        raise Problem(502, "source-failed", str(e)) from None
    finally:
        apply_egress(srv)


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
        for r in s.query(Receipt).filter(
            Receipt.deleted.is_(False), Receipt.filePrunedAt.is_(None)
        ):
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
        except OSError, ValueError:
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


# ---- Storage and file pruning (S16.17, S14.10) ----


class Size(Model):
    files: int
    bytes: int


class CategorySize(Size):
    category: str


class YearSizes(Model):
    year: int
    categories: list[CategorySize]


class StorageOut(Model):
    databaseBytes: int
    receiptsBytes: int
    expired: Size
    later: Size  # expiring later, or kept while what they belong to is open
    forever: Size
    pruned: int  # files pruned before
    byYear: list[YearSizes]  # what expires each coming year, by category
    expiredBy: list[CategorySize]  # what can be pruned now, by category
    keepStatementsYears: int | None


def _size(g) -> Size:
    return Size(files=g.files, bytes=g.bytes)


@router.get("/settings/storage", response_model=StorageOut)
def storage(request: Request, c: Caller = Depends(admin)):
    """Sizes and counts only, never what the files hold (S14.10.4)."""
    from ..receipts import retention

    srv = server(request)
    with srv.db.read() as s:
        st = retention.storage(s, srv.config.receipts_dir)
        return StorageOut(
            databaseBytes=_database_bytes(s),
            receiptsBytes=st.receiptsBytes,
            expired=_size(st.expired),
            later=_size(st.later),
            forever=_size(st.forever),
            pruned=st.pruned,
            byYear=[
                YearSizes(
                    year=y,
                    categories=[
                        CategorySize(category=k, files=g.files, bytes=g.bytes)
                        for k, g in sorted(cats.items())
                    ],
                )
                for y, cats in st.byYear.items()
            ],
            expiredBy=[
                CategorySize(category=k, files=g.files, bytes=g.bytes)
                for k, g in sorted(st.expiredBy.items())
            ],
            keepStatementsYears=settings.get(s, "keepStatementsYears"),
        )


class PruneIn(Model):
    categories: list[str]  # those ticked in the preview
    count: int  # typed by the admin, to confirm


class PruneOut(Model):
    files: int
    bytes: int
    backup: str


@router.post("/settings/storage/prune", response_model=PruneOut)
def prune_files(body: PruneIn, request: Request, c: Caller = Depends(admin)):
    """Remove the expired files of the categories ticked: a verified backup first, then the
    files, keeping every record; recorded in Activity with its counts (S14.10.5)."""
    from ..errors import refuse
    from ..receipts import retention
    from ..store import maintenance
    from .deps import recent_auth

    recent_auth(c)
    srv = server(request)
    with srv.db.read() as s:
        rows = retention.prunable(s, body.categories)
    if not rows:
        raise refuse("categories", "nothing-to-prune", "No expired files in what is ticked.")
    if body.count != len(rows):
        raise refuse("count", "count-mismatch", f"Type {len(rows):,} to prune them.")
    made = maintenance.backup(srv.config, srv.store)
    with srv.db.tx() as s:
        rows = retention.prunable(s, body.categories)
        freed = retention.prune_files(s, srv.config.receipts_dir, rows, c.id)
        activity.record(
            s,
            "files.pruned",
            actor=c.id,
            for_admins=True,
            detail={"files": len(rows), "bytes": freed, "categories": body.categories},
        )
    return PruneOut(files=len(rows), bytes=freed, backup=made.name)
