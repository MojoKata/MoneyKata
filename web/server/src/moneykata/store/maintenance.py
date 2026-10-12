"""Opening the database at start, backups (requirements §17.6) and the maintenance shell
(§17.7)."""

import datetime as dt
import hashlib
import json
import logging
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from .. import clock
from ..config import Config, RefuseStart
from ..keys import master
from . import copy, mapping, migrate
from .db import Database, WrongKey, connect, make_engine

log = logging.getLogger("moneykata.store")
BACKUP_PREFIX = "moneykata-"


@dataclass
class Store:
    db: Database
    keys: master.Unlocked


def next_keyring(config: Config) -> Path:
    return config.keyring_path.with_name(config.keyring_path.name + ".next")


def open_store(config: Config, migrate_copies: bool = True) -> Store:
    """Unwrap the data key, open the database with it, and bring it to this release."""
    mapping.map_all()
    unlocked = master.open_keys(config)
    config.data_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    if next_keyring(config).exists():
        unlocked = _finish_reencrypt(config, unlocked)
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
        engine, config.db_path, key, config.data_dir / "pre-upgrade" if migrate_copies else None
    )
    return Store(Database(engine), unlocked)


def reencrypt(config: Config, store: Store) -> Store:
    """A new data key (§18.7.2): the database is re-keyed and every secret gets a fresh data
    key and nonce. The master key is unchanged. The new keyring is written aside first, so an
    interrupted run is finished at the next start."""
    master_key = master.check_key_file(config.key_file, config.data_dir, config.backup_dir)
    old = store.keys
    ring = master.wrap(master_key, master.new_data_key(), old.ring.master_created, master.now())
    master.write_keyring(next_keyring(config), ring)
    new = master.Unlocked(
        old.master_id, ring, master.DataKeys.derive(master.unwrap(master_key, ring))
    )
    with store.db.engine.connect() as conn:
        conn.connection.dbapi_connection.execute(f'PRAGMA rekey = "{new.keys.sqlcipher_key}"')
    store.db.dispose()
    store = Store(Database(make_engine(config.db_path, new.keys.sqlcipher_key)), new)
    _rewrap_secrets(store.db, old.keys.secrets, new.keys.secrets)
    os.replace(next_keyring(config), config.keyring_path)
    log.info("re-encrypted under a new data key")
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


def _finish_reencrypt(config: Config, current: master.Unlocked) -> master.Unlocked:
    """A re-encryption was interrupted: use whichever key the database opens with."""
    master_key = master.check_key_file(config.key_file, config.data_dir, config.backup_dir)
    ring = master.read_keyring(next_keyring(config))
    pending = master.Unlocked(
        current.master_id, ring, master.DataKeys.derive(master.unwrap(master_key, ring))
    )
    try:
        connect(config.db_path, pending.keys.sqlcipher_key).close()
    except WrongKey:
        next_keyring(config).unlink()
        log.warning("an interrupted re-encryption had not started; it was dropped")
        return current
    mapping.map_all()
    db = Database(make_engine(config.db_path, pending.keys.sqlcipher_key))
    _rewrap_secrets(db, current.keys.secrets, pending.keys.secrets)
    db.dispose()
    os.replace(next_keyring(config), config.keyring_path)
    log.warning("finished an interrupted re-encryption")
    return pending


def record_key_event(config: Config, kind: str, detail: dict) -> None:
    """A key command run on the host, recorded in Activity for admins (§18.7.4)."""
    from ..activity import record

    try:
        store = open_store(config)
    except RefuseStart as e:
        log.warning("could not record %s in Activity: %s", kind, e)
        return
    with store.db.tx() as s:
        record(s, kind, actor=None, via="host", for_admins=True, detail=detail)
    store.db.dispose()


# ---------- backups ----------


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def backup(config: Config, store: Store, now: dt.datetime | None = None) -> Path:
    """One verified copy of the database, the keyring and the receipts directory. Every file
    in it is as encrypted as the data is: it opens only with the master key or its phrase."""
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
    if config.receipts_dir.is_dir():
        shutil.copytree(config.receipts_dir, part / "receipts")
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
    (part / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
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


def check_backup(path: Path, master_key: bytes) -> None:
    """A backup is whole and opens with this master key: the restore a check rehearses."""
    manifest = json.loads((path / "manifest.json").read_text())
    for rel, meta in manifest["files"].items():
        if _sha256(path / rel) != meta["sha256"]:
            raise RuntimeError(f"{rel} in {path.name} has changed since the backup")
    ring = master.read_keyring(path / "keyring")
    data_key = master.unwrap(master_key, ring)
    copy.verify(path / "moneykata.db", master.DataKeys.derive(data_key).sqlcipher_key)


# ---------- the maintenance shell ----------


def shell(config: Config) -> int:
    """`moneykata db shell`: SQL against the open database, as root on the host, with the key
    from the key file. Secrets stay encrypted even here (§18.3.4)."""
    unlocked = master.open_keys(config)
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
