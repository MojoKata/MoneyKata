"""Opening the database at start, backups (requirements S14.6), restoring one (S15.6.8), the
data directory's lock, and the maintenance shell (S14.7)."""

import datetime as dt
import fcntl
import hashlib
import json
import logging
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .. import clock
from ..config import Config, RefuseStart
from ..keys import master
from . import copy, mapping, migrate
from .db import Database, WrongKey, connect, make_engine

log = logging.getLogger("moneykata.store")
BACKUP_PREFIX = "moneykata-"
LOCK_FILE = "moneykata.lock"
# What a restore replaces in the data directory. Linked copies go too: they are left out of
# backups and pulled again from their sources (S11.9.9). The receipts stay in place: a backup
# is the database and its keyring only, the host backs up the files (S14.6). The TLS pair, the
# mail folder, the outbox and the pre-upgrade copies stay.
RESTORED = ("moneykata.db", "moneykata.db-wal", "moneykata.db-shm", "keyring", "links")


def lock_data_dir(config: Config, why: str):
    """Hold the data directory's lock: the server holds it while it runs, and a restore takes
    it, so neither starts while the other has the directory. Returns the open lock file; the
    lock lasts until it is closed or the process ends."""
    config.data_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    f = open(config.data_dir / LOCK_FILE, "a")  # noqa: SIM115 - held for the process's life
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        f.close()
        raise RefuseStart(f"{config.data_dir} is in use by a running MoneyKata; {why}") from None
    return f


@dataclass
class Store:
    db: Database
    keys: master.Unlocked


def next_keyring(config: Config) -> Path:
    return config.keyring_path.with_name(config.keyring_path.name + ".next")


def open_store(config: Config, master_key: bytes, migrate_copies: bool = True) -> Store:
    """Unwrap the data key with the phrase's key, open the database with it, and bring it to
    this release. The master key is used here and not kept."""
    mapping.map_all()
    unlocked = master.unlock_keys(config, master_key)
    config.data_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    if next_keyring(config).exists():
        unlocked = _finish_reencrypt(config, unlocked, master_key)
    key = unlocked.keys.sqlcipher_key
    engine = make_engine(config.db_path, key)
    try:
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
    except WrongKey:
        raise RefuseStart(
            f"{config.db_path} does not open with the data key from {config.keyring_path.name}"
        ) from None
    except Exception as e:
        raise RefuseStart(f"{config.db_path} cannot be opened: {type(e).__name__}") from None
    if config.db_path.exists():
        os.chmod(config.db_path, 0o600)
    migrate.upgrade(
        engine,
        config.db_path,
        key,
        config.data_dir / "pre-upgrade" if migrate_copies else None,
        config.keyring_path,
    )
    return Store(Database(engine), unlocked)


def reencrypt(
    config: Config, store: Store, master_key: bytes, choices: dict[str, str] | None = None
) -> Store:
    """A new data key (S15.7.2): the database is re-keyed and every secret gets a fresh data
    key and nonce. The master key, typed again for this, is unchanged. The new keyring is
    written aside first, so an interrupted run is finished at the next unlock. Then each copy
    on the host is rewritten, deleted or left as its choice says (`copies`)."""
    if master.key_id(master_key) != store.keys.master_id:
        raise master.WrongPhrase("those words are not this server's key")
    old = store.keys
    data_key = master.new_data_key()
    ring = master.wrap(
        master_key, data_key, old.ring.master_created, master.now(), old.ring.previous
    )
    master.write_keyring(next_keyring(config), ring)
    new = master.Unlocked(old.master_id, ring, master.DataKeys.derive(data_key), data_key)
    with store.db.engine.connect() as conn:
        conn.connection.dbapi_connection.execute(f'PRAGMA rekey = "{new.keys.sqlcipher_key}"')
    store.db.dispose()
    store = Store(Database(make_engine(config.db_path, new.keys.sqlcipher_key)), new)
    _rewrap_secrets(store.db, old.keys.secrets, new.keys.secrets)
    _rewrap_receipts(config.receipts_dir, old.keys.receipts, new.keys.receipts)
    os.replace(next_keyring(config), config.keyring_path)
    log.info("re-encrypted under a new data key")
    if choices:
        from . import copies

        for name, outcome in copies.apply_reencryption(
            config, choices, master_key, data_key
        ).items():
            log.info("copy %s: %s", name, outcome)
    return store


def _rewrap_secrets(db: Database, old_key: bytes, new_key: bytes) -> int:
    from ..keys import secrets as sealing
    from .entities.core import Secret

    n = 0
    with db.tx() as s:
        for row in s.query(Secret):
            sealed = sealing.Sealed(row.ciphertext, row.nonce, row.wrappedKey)
            try:
                sealing.open_sealed(new_key, sealed, row.recordType, row.recordId, row.field)
                continue  # done before an interruption
            except sealing.SecretError:
                pass
            fresh = sealing.rewrap(
                old_key, new_key, sealed, row.recordType, row.recordId, row.field
            )
            row.ciphertext, row.nonce, row.wrappedKey = (
                fresh.ciphertext,
                fresh.nonce,
                fresh.wrappedKey,
            )
            n += 1
    return n


def _rewrap_receipts(folder: Path, old_key, new_key) -> int:
    """Each receipt file again under the new receipts key, one at a time; a file that already
    opens with the new key was done before an interruption."""
    from ..keys import files

    n = 0
    if not folder.is_dir():
        return 0
    for path in sorted(folder.glob("*.mkr")):
        name = path.stem
        try:
            for _ in files.open_stream(path, new_key, name):
                pass
            continue
        except files.FileError:
            pass
        files.write(path, files.open_stream(path, old_key, name), new_key.public_key(), name)
        n += 1
    return n


def _finish_reencrypt(
    config: Config, current: master.Unlocked, master_key: bytes
) -> master.Unlocked:
    """A re-encryption was interrupted: use whichever key the database opens with. It is
    finished here, at the unlock, with the phrase just given; a pending keyring wrapped under
    another phrase (a rotation in between) is refused by name rather than crashed on."""
    ring = master.read_keyring(next_keyring(config))
    try:
        data_key = master.unwrap(master_key, ring)
    except ValueError:
        raise RefuseStart(
            f"a re-encryption is pending under {master.fingerprint(ring.master_id)}: unlock "
            "with that phrase so it can finish"
        ) from None
    pending = master.Unlocked(current.master_id, ring, master.DataKeys.derive(data_key), data_key)
    try:
        connect(config.db_path, pending.keys.sqlcipher_key).close()
    except WrongKey:
        next_keyring(config).unlink()
        log.warning("an interrupted re-encryption had not started; it was dropped")
        return current
    mapping.map_all()
    db = Database(make_engine(config.db_path, pending.keys.sqlcipher_key))
    _rewrap_secrets(db, current.keys.secrets, pending.keys.secrets)
    _rewrap_receipts(config.receipts_dir, current.keys.receipts, pending.keys.receipts)
    db.dispose()
    os.replace(next_keyring(config), config.keyring_path)
    log.warning("finished an interrupted re-encryption")
    return pending


HOST_EVENTS = "host-events.jsonl"


def queue_host_event(config: Config, kind: str, detail: dict) -> None:
    """A command run on the host, queued for Activity (S15.7.4): a one-off container has no
    phrase to open the database with, so the running server takes the queue at its next
    unlock and every quarter hour (`take_host_events`)."""
    config.data_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    line = json.dumps({"kind": kind, "at": clock.now().isoformat(), "detail": detail})
    path = config.data_dir / HOST_EVENTS
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, "a") as f:
        f.write(line + "\n")
    if os.geteuid() == 0:
        os.chown(path, 10001, 10001)


def take_host_events(config: Config) -> list[dict]:
    """The queued host events, removed from the queue."""
    path = config.data_dir / HOST_EVENTS
    try:
        text = path.read_text()
    except FileNotFoundError:
        return []
    path.unlink()
    out = []
    for line in text.splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


# ---------- backups ----------


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def backup(config: Config, store: Store, now: dt.datetime | None = None) -> Path:
    """One verified, coherent copy of the database with its keyring (S14.6). Never the receipt
    files: the host backs up the data directory, and this copy exists so that the live
    database the host picks up has a consistent twin beside it. It opens only with the
    phrase."""
    now = now or clock.now()
    name = BACKUP_PREFIX + now.strftime("%Y%m%d-%H%M%S")
    config.backup_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    part = config.backup_dir / (name + ".part")
    if part.exists():
        shutil.rmtree(part)
    part.mkdir(mode=0o700)
    key = store.keys.keys.sqlcipher_key
    copy.export(store.db.engine, part / "moneykata.db", key)
    copy.verify(part / "moneykata.db", key)
    shutil.copy2(config.keyring_path, part / "keyring")
    os.chmod(part / "keyring", 0o600)
    files = {
        str(p.relative_to(part)): {"bytes": p.stat().st_size, "sha256": _sha256(p)}
        for p in sorted(part.rglob("*"))
        if p.is_file()
    }
    manifest = {
        "format": "moneykata-backup-1",
        "made": now.isoformat(),
        "server": config.name,
        "masterKey": master.fingerprint(store.keys.master_id),
        "revision": migrate.current(store.db.engine),
        "files": files,
    }
    write_manifest(part / "manifest.json", manifest, store.keys.data_key)
    final = config.backup_dir / name
    os.replace(part, final)
    log.info("backup %s made and verified", name)
    return final


def backups(config: Config) -> list[Path]:
    if not config.backup_dir.is_dir():
        return []
    return sorted(
        p
        for p in config.backup_dir.iterdir()
        if p.is_dir() and p.name.startswith(BACKUP_PREFIX) and not p.name.endswith(".part")
    )


def prune(config: Config, keep: int) -> list[Path]:
    gone = backups(config)[:-keep] if keep > 0 else []
    for p in gone:
        shutil.rmtree(p)
        log.info("backup %s pruned", p.name)
    return gone


def manifest_mac(manifest: dict, data_key: bytes) -> str:
    """The manifest's authentication code (S14.6): HMAC-SHA256 under a key derived from the
    data key, over everything but the code itself, so a backup swapped for an older one, or a
    manifest rewritten to match a changed file, is caught by whoever holds the phrase."""
    import hmac

    body = json.dumps({k: v for k, v in manifest.items() if k != "mac"}, sort_keys=True)
    return hmac.new(
        master.hkdf(data_key, "moneykata backup manifest"), body.encode(), hashlib.sha256
    ).hexdigest()


def write_manifest(path: Path, manifest: dict, data_key: bytes) -> None:
    manifest = {k: v for k, v in manifest.items() if k != "mac"}
    manifest["mac"] = manifest_mac(manifest, data_key)
    path.write_text(json.dumps(manifest, indent=2) + "\n")


def check_backup(path: Path, master_key: bytes) -> None:
    """A backup is whole, its manifest is its own, and it opens with this master key: the
    restore a check rehearses."""
    manifest = json.loads((path / "manifest.json").read_text())
    for rel, meta in manifest["files"].items():
        if _sha256(path / rel) != meta["sha256"]:
            raise RuntimeError(f"{rel} in {path.name} has changed since the backup")
    ring = master.read_keyring(path / "keyring")
    data_key = master.unwrap(master_key, ring)
    import hmac

    if not hmac.compare_digest(manifest.get("mac", ""), manifest_mac(manifest, data_key)):
        raise RuntimeError(f"the manifest of {path.name} is not the one its backup wrote")
    # Opened from a scratch copy: opening sets the journal mode, which rewrites the file's
    # header, and the backup must stay as its manifest describes it.
    with tempfile.TemporaryDirectory() as tmp:
        scratch = Path(tmp) / "moneykata.db"
        shutil.copy2(path / "moneykata.db", scratch)
        copy.verify(scratch, master.DataKeys.derive(data_key).sqlcipher_key)


def verify_backup(config: Config, master_key: bytes, path: Path | None = None) -> Path:
    """`moneykata db verify-backup`: a backup (the newest by default) is whole and opens with
    the phrase typed, which may be a previous one for a backup made before a rotation: the
    drill operations.md asks for."""
    if path is None:
        made = backups(config)
        if not made:
            raise RefuseStart(f"there is no backup in {config.backup_dir}")
        path = made[-1]
    try:
        check_backup(path, master_key)
    except ValueError as e:
        raise RefuseStart(f"{path.name} does not open with that phrase: {e}") from None
    return path


def restore(
    config: Config, backup_path: Path, master_key: bytes, now: dt.datetime | None = None
) -> Path:
    """`moneykata db restore`, with the server stopped: check the backup opens with the phrase
    typed, move what it replaces aside into `before-restore-<time>/` in the data directory, and
    copy it in. The server's next unlock opens it and migrates it if it is from an earlier
    release. Returns the folder the replaced files went to."""
    lock = lock_data_dir(config, "stop the server before restoring")
    try:
        verify_backup(config, master_key, backup_path)
        manifest = json.loads((backup_path / "manifest.json").read_text())
        revision = manifest.get("revision")
        if revision is not None and revision not in migrate.known():
            raise RefuseStart(
                f"{backup_path.name} is at revision {revision}, from a newer MoneyKata than "
                "this one; restore it with that release or a later one"
            )
        stamp = (now or clock.now()).strftime("%Y%m%d-%H%M%S")
        aside = config.data_dir / f"before-restore-{stamp}"
        aside.mkdir(mode=0o700)
        for name in RESTORED:
            if (config.data_dir / name).exists():
                os.replace(config.data_dir / name, aside / name)
        shutil.copy2(backup_path / "moneykata.db", config.db_path)
        shutil.copy2(backup_path / "keyring", config.keyring_path)
        for p in (config.db_path, config.keyring_path):
            os.chmod(p, 0o600)
        log.info("restored %s; the files it replaced are in %s", backup_path.name, aside.name)
        return aside
    finally:
        lock.close()


# ---------- the maintenance shell ----------


def shell(config: Config, master_key: bytes) -> int:
    """`moneykata db shell`: SQL against the database, on the host, with the phrase typed.
    Secrets stay encrypted even here (S15.3.4)."""
    try:
        unlocked = master.unlock_keys(config, master_key)
    except master.WrongPhrase as e:
        raise RefuseStart(str(e)) from None
    try:
        conn = connect(config.db_path, unlocked.keys.sqlcipher_key)
    except WrongKey as e:
        raise RefuseStart(str(e)) from None
    print(f"{config.db_path} ({master.fingerprint(unlocked.master_id)}). End with Ctrl-D.")
    buf = ""
    while True:
        try:
            line = input("sql> " if not buf else "...> ")
        except EOFError:
            print()
            break
        buf += line + "\n"
        if not buf.strip().endswith(";"):
            continue
        try:
            cur = conn.execute(buf)
            rows = cur.fetchall()
            if cur.description:
                print(" | ".join(d[0] for d in cur.description))
            for r in rows:
                print(" | ".join("" if v is None else str(v) for v in r))
        except Exception as e:
            print(f"error: {e}")
        buf = ""
    conn.close()
    return 0


def rotate_running(
    config: Config,
    store: Store,
    new_master: bytes,
    choices: dict[str, str] | None = None,
    old_master: bytes | None = None,
) -> tuple[Store, dict[str, str]]:
    """Rotation through the running server (S15.7.1): it holds the data key, so no old phrase
    is needed; the keyring is written again under the new master key, the old one recorded.
    Then each copy on the host is re-wrapped, deleted or left as its choice says; a copy
    under an earlier data key can be re-wrapped only when the old phrase was given too."""
    from . import copies

    if next_keyring(config).exists():
        raise RefuseStart("a re-encryption is pending: it finishes at the next unlock")
    at = master.now()
    ring = master.rotated(store.keys.ring, store.keys.data_key, new_master, at)
    master.write_keyring(config.keyring_path, ring)
    new = master.Unlocked(ring.master_id, ring, store.keys.keys, store.keys.data_key)
    outcomes = copies.apply_rotation(config, choices or {}, store.keys, new_master, at, old_master)
    return Store(store.db, new), outcomes
