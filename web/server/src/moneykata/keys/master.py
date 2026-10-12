"""The three levels of keys (requirements §18.3).

The **master key** (128 bits) sits in one file on the host and wraps one thing: the **data
key** (256 bits), kept wrapped in the data directory's `keyring`, so it travels with every
backup. From the data key HKDF-SHA256 derives the database key, the receipts key pair and the
secrets key, each under its own label.
"""

import base64
import datetime as dt
import hashlib
import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .. import clock
from ..config import Config, RefuseStart

KEY_BYTES = 16
DATA_KEY_BYTES = 32
KEYRING_FORMAT = "moneykata-keyring-1"


def hkdf(key: bytes, label: str, length: int = 32) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=length, salt=None, info=label.encode()).derive(
        key
    )


def key_id(master: bytes) -> str:
    """The first 16 hex digits of SHA-256("moneykata key id" ‖ key) (§18.3.5)."""
    return hashlib.sha256(b"moneykata key id" + master).hexdigest()[:16]


def fingerprint(master_or_id: bytes | str) -> str:
    """The short form shown in Settings and on the recovery sheet: mk-3f9a…c21e."""
    kid = master_or_id if isinstance(master_or_id, str) else key_id(master_or_id)
    return f"mk-{kid[:4]}…{kid[-4:]}"


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode()


def _unb64(s: str) -> bytes:
    return base64.b64decode(s, validate=True)


def now() -> dt.datetime:
    return clock.now().replace(microsecond=0)


# ---------- the key file ----------


def check_key_file(path: Path, data_dir: Path, backup_dir: Path) -> bytes:
    """Read the master key, refusing every condition of §18.4.4."""
    try:
        st = os.lstat(path)
    except FileNotFoundError:
        raise RefuseStart(
            f"the master key {path} does not exist; make it with `moneykata keys init`"
        ) from None
    except PermissionError:
        raise RefuseStart(f"the master key {path} cannot be reached by this account") from None
    if not stat.S_ISREG(st.st_mode):
        raise RefuseStart(f"the master key {path} is not a regular file")
    resolved = path.resolve()
    for d, label in ((data_dir, "data"), (backup_dir, "backup")):
        if resolved.is_relative_to(d.resolve()):
            raise RefuseStart(f"the master key {path} is inside the {label} directory")
    mode = stat.S_IMODE(st.st_mode)
    if mode & 0o044:
        raise RefuseStart(
            f"the master key {path} can be read by others (mode {mode:04o}; it must be 0400)"
        )
    if mode & 0o022 or (mode & 0o200 and st.st_uid != 0):
        raise RefuseStart(
            f"the master key {path} can be written by an account other than "
            f"root (mode {mode:04o}; it must be 0400)"
        )
    if st.st_size != KEY_BYTES:
        raise RefuseStart(f"the master key {path} is not exactly {KEY_BYTES} bytes")
    try:
        data = path.read_bytes()
    except PermissionError:
        raise RefuseStart(f"the master key {path} cannot be read by this account") from None
    if len(data) != KEY_BYTES:
        raise RefuseStart(f"the master key {path} is not exactly {KEY_BYTES} bytes")
    return data


def write_key_file(path: Path, master: bytes, owner: int | None = None) -> None:
    """Write a new key file, mode 0400, refusing to overwrite one."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o400)
    try:
        os.write(fd, master)
        os.fsync(fd)
    finally:
        os.close(fd)
    if owner is not None:
        os.chown(path, owner, owner)


# ---------- the keyring: the wrapped data key ----------


@dataclass(frozen=True)
class Keyring:
    master_id: str
    master_created: dt.datetime
    data_key_created: dt.datetime
    nonce: bytes
    wrapped: bytes

    def to_json(self) -> str:
        return (
            json.dumps(
                {
                    "format": KEYRING_FORMAT,
                    "masterKeyId": self.master_id,
                    "masterCreatedAt": self.master_created.isoformat(),
                    "dataKeyCreatedAt": self.data_key_created.isoformat(),
                    "nonce": _b64(self.nonce),
                    "wrapped": _b64(self.wrapped),
                },
                indent=2,
            )
            + "\n"
        )

    @staticmethod
    def from_json(text: str) -> "Keyring":
        d = json.loads(text)
        if d.get("format") != KEYRING_FORMAT:
            raise ValueError("not a MoneyKata keyring")
        return Keyring(
            d["masterKeyId"],
            dt.datetime.fromisoformat(d["masterCreatedAt"]),
            dt.datetime.fromisoformat(d["dataKeyCreatedAt"]),
            _unb64(d["nonce"]),
            _unb64(d["wrapped"]),
        )


def _aad(master_id: str) -> bytes:
    return b"moneykata keyring|" + master_id.encode()


def wrap(
    master: bytes, data_key: bytes, master_created: dt.datetime, data_key_created: dt.datetime
) -> Keyring:
    nonce = os.urandom(12)
    mid = key_id(master)
    sealed = AESGCM(hkdf(master, "moneykata master")).encrypt(nonce, data_key, _aad(mid))
    return Keyring(mid, master_created, data_key_created, nonce, sealed)


def unwrap(master: bytes, ring: Keyring) -> bytes:
    if key_id(master) != ring.master_id:
        raise ValueError(
            f"the data key was wrapped by {fingerprint(ring.master_id)}, not by "
            f"{fingerprint(master)}"
        )
    try:
        return AESGCM(hkdf(master, "moneykata master")).decrypt(
            ring.nonce, ring.wrapped, _aad(ring.master_id)
        )
    except InvalidTag:
        raise ValueError("the master key does not unwrap the data key") from None


def write_keyring(path: Path, ring: Keyring, owner: int | None = None) -> None:
    """Replace the keyring atomically: written beside it, synced, then renamed."""
    tmp = path.with_name(path.name + ".new")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(ring.to_json())
        f.flush()
        os.fsync(f.fileno())
    if owner is not None:
        os.chown(tmp, owner, owner)
    os.replace(tmp, path)


def read_keyring(path: Path) -> Keyring:
    try:
        return Keyring.from_json(path.read_text())
    except FileNotFoundError:
        raise RefuseStart(
            f"the keyring {path} is missing; restore it from a backup, or run "
            "`moneykata keys init` on a new server"
        ) from None
    except (ValueError, KeyError) as e:
        raise RefuseStart(f"the keyring {path} cannot be read: {e}") from None


# ---------- what the data key gives ----------


@dataclass(frozen=True)
class DataKeys:
    """The keys derived from the data key (§18.3.2), held for the server's lifetime."""

    database: bytes
    receipts: X25519PrivateKey
    secrets: bytes

    @staticmethod
    def derive(data_key: bytes) -> "DataKeys":
        return DataKeys(
            database=hkdf(data_key, "moneykata database"),
            receipts=X25519PrivateKey.from_private_bytes(hkdf(data_key, "moneykata receipts")),
            secrets=hkdf(data_key, "moneykata secrets"),
        )

    @property
    def sqlcipher_key(self) -> str:
        return f"x'{self.database.hex()}'"


@dataclass(frozen=True)
class Unlocked:
    master_id: str
    ring: Keyring
    keys: DataKeys


def open_keys(config: Config) -> Unlocked:
    """At start: read the key file, check it, and unwrap the data key with it."""
    master = check_key_file(config.key_file, config.data_dir, config.backup_dir)
    ring = read_keyring(config.keyring_path)
    try:
        data_key = unwrap(master, ring)
    except ValueError as e:
        raise RefuseStart(str(e)) from None
    return Unlocked(key_id(master), ring, DataKeys.derive(data_key))


def new_data_key() -> bytes:
    return os.urandom(DATA_KEY_BYTES)


def new_master() -> bytes:
    return os.urandom(KEY_BYTES)
