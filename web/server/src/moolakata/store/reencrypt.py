"""Re-encryption under a new data key (requirements S15.7.2), as a journal, run only while the
server isn't serving: at an unlock, before it serves, or on the host with the server stopped.

`reencrypt.json` in the data directory records each step before it is taken, and the copies'
choices among them; the new data key's keyring is written beside the keyring as
`keyring.next`, and the old one kept as `keyring.old` until the copies are done. Every step is
safe to take again, so an interrupted run carries on from the journal at the next unlock, with
the phrase given then, redoing nothing. A receipt that opens under neither key goes to
`receipts-set-aside/`, a secret that opens under neither stays as it is, and both are reported,
never fatal. A `keyring.next` the journal doesn't explain is set aside, never deleted.

The same per-file re-wrap serves a restore (S15.6.8), whose receipts may be under the key a
re-encryption replaced."""

import datetime as dt
import json
import logging
import os
import shutil
import threading
from dataclasses import dataclass, field
from pathlib import Path

from .. import clock
from ..config import Config, RefuseStart
from ..keys import files, master
from . import copies, copy, mapping
from .db import Database, WrongKey, connect, make_engine

log = logging.getLogger("moolakata.store")
JOURNAL = "reencrypt.json"
REPORT = "reencrypt-report.json"
OLD = "keyring.old"
SET_ASIDE = "receipts-set-aside"
CHOICES = ("reencrypt", "delete", "leave")


@dataclass
class Progress:
    """Where a run is, for the locked screen and Settings (S15.7.2)."""

    stage: str = "starting"
    done: int = 0
    total: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def set(self, stage: str, done: int = 0, total: int = 0) -> None:
        with self.lock:
            self.stage, self.done, self.total = stage, done, total

    def as_dict(self) -> dict:
        with self.lock:
            return {"stage": self.stage, "done": self.done, "total": self.total}


def _path(config: Config) -> Path:
    return config.data_dir / JOURNAL


def next_keyring(config: Config) -> Path:
    return config.keyring_path.with_name(config.keyring_path.name + ".next")


def _write(path: Path, data: dict) -> None:
    tmp = path.with_name(path.name + ".new")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(data, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    copies.chown_to_server(path)


def journal(config: Config) -> dict | None:
    try:
        return json.loads(_path(config).read_text())
    except FileNotFoundError:
        return None
    except ValueError:
        raise RefuseStart(f"{_path(config)} cannot be read: set it aside and start again") from None


def pending(config: Config) -> bool:
    """A re-encryption scheduled or interrupted: the next unlock runs it before serving."""
    return _path(config).exists() or next_keyring(config).exists()


def schedule(config: Config, choices: dict[str, str], by: str | None, why: str) -> dict:
    """A re-encryption for the next unlock (Settings › Key storage, or a rotation through the
    running server), with each copy's choice. The phrase is the one given at that unlock."""
    if any(v not in CHOICES for v in choices.values()):
        raise ValueError("each copy: reencrypt, delete or leave")
    have = journal(config)
    if have is not None and have.get("steps"):
        raise RefuseStart("a re-encryption is under way: it finishes at the next unlock")
    j = {
        "why": why,
        "scheduledAt": clock.now().isoformat(),
        "by": by,
        "copies": dict(choices),
        "steps": {},
    }
    _write(_path(config), j)
    return j


def cancel(config: Config) -> bool:
    """A scheduled re-encryption not yet begun, cancelled; one under way can't be."""
    j = journal(config)
    if j is None or j.get("steps"):
        return False
    _path(config).unlink()
    return True


def report(config: Config) -> dict | None:
    """What the last run left: files and secrets set aside, and each copy's outcome."""
    try:
        return json.loads((config.data_dir / REPORT).read_text())
    except FileNotFoundError, ValueError:
        return None


def _step(config: Config, j: dict, name: str, value) -> None:
    j["steps"][name] = value
    _write(_path(config), j)


def opens(path: Path, key, name: str) -> bool:
    """Whether a receipt file opens under a key: its first chunk decides."""
    try:
        next(files.open_stream(path, key, name))
        return True
    except files.FileError, OSError, StopIteration:
        return False


def rewrap_files(folder: Path, old_key, new_key, progress: Progress | None = None) -> list[str]:
    """Each receipt file under the new receipts key: one already under it is left, one under
    the old key rewritten, and one under neither moved to `receipts-set-aside/`. Returns the
    names set aside. Safe to run again after an interruption."""
    aside: list[str] = []
    if not folder.is_dir():
        return aside
    paths = sorted(folder.glob("*.mkr"))
    for i, path in enumerate(paths):
        if progress is not None and i % 25 == 0:
            progress.set("receipts", i, len(paths))
        name = path.stem
        if opens(path, new_key, name):
            continue
        if opens(path, old_key, name):
            files.write(path, files.open_stream(path, old_key, name), new_key.public_key(), name)
            continue
        target = folder.parent / SET_ASIDE
        target.mkdir(mode=0o700, exist_ok=True)
        os.replace(path, target / path.name)
        aside.append(path.name)
        log.warning("receipt file %s opens under neither key: set aside", path.name)
    if progress is not None:
        progress.set("receipts", len(paths), len(paths))
    return aside


def _rewrap_secrets(db: Database, old_key: bytes, new_key: bytes) -> list[str]:
    """Each secret under a fresh data key and nonce, wrapped under the new secrets key; one
    already done is left, and one that opens under neither key is named, not fatal."""
    from ..keys import secrets as sealing
    from .entities.core import Secret

    aside = []
    with db.tx() as s:
        for row in s.query(Secret):
            sealed = sealing.Sealed(row.ciphertext, row.nonce, row.wrappedKey)
            try:
                sealing.open_sealed(new_key, sealed, row.recordType, row.recordId, row.field)
                continue
            except sealing.SecretError:
                pass
            try:
                fresh = sealing.rewrap(
                    old_key, new_key, sealed, row.recordType, row.recordId, row.field
                )
            except sealing.SecretError:
                aside.append(f"{row.recordType}/{row.recordId}/{row.field}")
                continue
            row.ciphertext, row.nonce, row.wrappedKey = (
                fresh.ciphertext,
                fresh.nonce,
                fresh.wrappedKey,
            )
    return aside


def _opens_db(config: Config, data_key: bytes) -> bool:
    try:
        connect(config.db_path, master.DataKeys.derive(data_key).sqlcipher_key).close()
        return True
    except WrongKey:
        return False


def check_phrase(config: Config, master_key: bytes) -> None:
    """Whether this phrase can carry the pending run, before the server says it is under way:
    the keyring and any `keyring.next` must both be its."""
    master.unlock_keys(config, master_key)
    nxt = next_keyring(config)
    if nxt.exists() and _path(config).exists():
        ring = master.read_keyring(nxt)
        if ring.master_id != master.key_id(master_key):
            raise RefuseStart(
                f"a re-encryption is pending under {master.fingerprint(ring.master_id)}: unlock "
                "with that phrase so it can finish"
            )


def run(config: Config, master_key: bytes, progress: Progress | None = None) -> dict | None:
    """Carry the journal's re-encryption to its end, with the server not serving. Returns the
    report, or None when nothing was pending."""
    progress = progress or Progress()
    j = journal(config)
    nxt = next_keyring(config)
    if j is None:
        if nxt.exists():
            stamp = clock.now().strftime("%Y%m%d-%H%M%S")
            os.replace(nxt, nxt.with_name(f"{nxt.name}.set-aside-{stamp}"))
            log.warning("a keyring.next that no journal explains was set aside")
        return None
    mapping.map_all()
    ring = master.read_keyring(config.keyring_path)
    steps = j["steps"]
    old_ring_path = config.data_dir / OLD
    if steps.get("keyring"):
        old_ring = master.read_keyring(old_ring_path)
        new_ring = ring
    else:
        old_ring = ring
        new_ring = master.read_keyring(nxt) if nxt.exists() else None
    try:
        old = master.unwrap(master_key, old_ring)
    except ValueError:
        raise master.WrongPhrase("those words are not this server's key") from None
    if new_ring is not None and new_ring.master_id != master.key_id(master_key):
        raise RefuseStart(
            f"a re-encryption is pending under {master.fingerprint(new_ring.master_id)}: unlock "
            "with that phrase so it can finish"
        )
    old_keys = master.DataKeys.derive(old)
    if not config.db_path.exists():  # a new server: no database yet, only the key to change
        steps.setdefault("backup", None)
        steps.setdefault("rekeyed", True)
        steps.setdefault("secrets", [])

    if "backup" not in steps:
        progress.set("backup")
        from .maintenance import Store, backup

        if _opens_db(config, old):
            st = Store(
                Database(make_engine(config.db_path, old_keys.sqlcipher_key)),
                master.Unlocked(old_ring.master_id, old_ring, old_keys, old),
            )
            try:
                made = backup(config, st)
            finally:
                st.db.dispose()
            _step(config, j, "backup", made.name)
        else:
            _step(config, j, "backup", None)  # already re-keyed: the backup came before
    if new_ring is None:
        new = master.new_data_key()
        new_ring = master.wrap(
            master_key, new, old_ring.master_created, master.now(), old_ring.previous
        )
        master.write_keyring(nxt, new_ring)
        copies.chown_to_server(nxt)
        _step(config, j, "next", new_ring.data_key_id)
    new = master.unwrap(master_key, new_ring)
    new_keys = master.DataKeys.derive(new)

    if not steps.get("rekeyed"):
        progress.set("database")
        if not _opens_db(config, new):
            if not _opens_db(config, old):
                raise RefuseStart(f"{config.db_path} opens under neither data key")
            copy.rekey(config.db_path, old_keys.sqlcipher_key, new_keys.sqlcipher_key)
        _step(config, j, "rekeyed", True)
    if "secrets" not in steps:
        progress.set("secrets")
        db = Database(make_engine(config.db_path, new_keys.sqlcipher_key))
        try:
            _step(config, j, "secrets", _rewrap_secrets(db, old_keys.secrets, new_keys.secrets))
        finally:
            db.dispose()
    if "receipts" not in steps:
        _step(
            config,
            j,
            "receipts",
            rewrap_files(config.receipts_dir, old_keys.receipts, new_keys.receipts, progress),
        )
    if not steps.get("keyring"):
        if not old_ring_path.exists():
            shutil.copy2(config.keyring_path, old_ring_path)
            os.chmod(old_ring_path, 0o600)
        os.replace(nxt, config.keyring_path)
        _step(config, j, "keyring", True)
    outcomes = dict(steps.get("copies") or {})
    found = copies.copies(config)
    progress.set("copies", 0, len(found))
    for i, c in enumerate(found):
        if c.name in outcomes:
            continue
        choice = j["copies"].get(c.name, "leave")
        outcomes[c.name] = _copy(c, choice, master_key, old, new)
        _step(config, j, "copies", outcomes)
        progress.set("copies", i + 1, len(found))
    done = {
        "why": j.get("why"),
        "finishedAt": clock.now().isoformat(),
        "backup": steps.get("backup"),
        "receiptsSetAside": steps.get("receipts") or [],
        "secretsSetAside": steps.get("secrets") or [],
        "copies": outcomes,
    }
    _write(config.data_dir / REPORT, done)
    old_ring_path.unlink(missing_ok=True)
    _path(config).unlink()
    progress.set("done")
    log.info("re-encrypted under a new data key")
    return done


def _copy(c: copies.Copy, choice: str, master_key: bytes, old: bytes, new: bytes) -> str:
    """One copy's choice: deleted, left, or rewritten under the new data key when it holds the
    one replaced or opens with this phrase; a copy under an earlier phrase, with an earlier
    data key, can only be left or deleted."""
    if choice == "delete":
        copies.remove(c)
        return "deleted"
    if choice != "reencrypt":
        return "left"
    if c.ring is None:
        return "left: its keyring cannot be read"
    if c.ring.data_key_id == master.data_key_id(new):
        return "already under the new data key"
    if c.ring.data_key_id == master.data_key_id(old):
        held = old
    elif c.ring.master_id == master.key_id(master_key):
        held = master.unwrap(master_key, c.ring)  # this phrase, an earlier data key
    else:
        return f"left: needs the phrase of {master.fingerprint(c.ring.master_id)}"
    copies.reencrypt_with(c, held, new, master_key)
    return "re-encrypted"


def at_once(config: Config, master_key: bytes, choices: dict[str, str], why: str) -> dict:
    """On the host, the server stopped (`keys reencrypt`, an offline rotation): scheduled and
    run in one go, the data directory's lock held."""
    from .maintenance import lock_data_dir

    lock = lock_data_dir(config, "stop the server first, or schedule it in Settings › Key storage")
    try:
        if journal(config) is None:
            schedule(config, choices, None, why)
        out = run(config, master_key)
        assert out is not None
        return out
    finally:
        lock.close()


def started_at(config: Config) -> dt.datetime | None:
    j = journal(config)
    try:
        return dt.datetime.fromisoformat(j["scheduledAt"]) if j else None
    except KeyError, ValueError:
        return None
