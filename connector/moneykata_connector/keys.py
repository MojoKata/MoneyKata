"""The connector's keys (requirements S18.4.2, S18.4.5), made at pairing: an identity key
(Ed25519) that signs its calls, kept beside the vault so a locked connector can still report,
and a sealing key (X25519) that credentials are sealed to, whose private half lives in the
vault (`vault.py`) and whose public half is kept here. With them, the server it is paired
with: its address and its link key's fingerprint. This file holds nothing that opens a
credential."""

import base64
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey


def b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def fingerprint(public: bytes) -> str:
    return hashlib.sha256(public).hexdigest()


def short(fp: str) -> str:
    return " ".join(fp[i : i + 4] for i in range(0, 16, 4))


@dataclass
class Pairing:
    address: str  # MoneyKata's address, from the pairing code
    server_fp: str  # its link key's fingerprint, whole
    identity: Ed25519PrivateKey
    sealing_public: bytes  # the private half is in the vault

    @property
    def identity_public(self) -> bytes:
        return self.identity.public_key().public_bytes_raw()

    @property
    def fingerprint(self) -> str:
        return fingerprint(self.identity_public)


def load(path: Path) -> Pairing | None:
    try:
        d = json.loads(path.read_text())
    except FileNotFoundError:
        return None
    return Pairing(
        d["address"],
        d["serverFingerprint"],
        Ed25519PrivateKey.from_private_bytes(unb64(d["identity"])),
        unb64(d["sealingPublic"]),
    )


def new_sealing_key() -> tuple[bytes, bytes]:
    """A sealing key pair as raw bytes: (private, for the vault; public, for MoneyKata)."""
    k = X25519PrivateKey.generate()
    return k.private_bytes_raw(), k.public_key().public_bytes_raw()


def make(path: Path, address: str, server_fp: str, sealing_public: bytes) -> Pairing:
    """A new identity key for a new pairing; the old pairing's keys go with it (S18.4.4)."""
    p = Pairing(address, server_fp, Ed25519PrivateKey.generate(), sealing_public)
    save(path, p)
    return p


def save(path: Path, p: Pairing) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(
            {
                "address": p.address,
                "serverFingerprint": p.server_fp,
                "identity": b64(p.identity.private_bytes_raw()),
                "sealingPublic": b64(p.sealing_public),
            },
            f,
        )


def forget(path: Path) -> None:
    if path.exists():
        path.unlink()
