"""Signed calls to MoolaKata (docs/connector-protocol.md §3): `MK-Conn-*` headers, an Ed25519
signature over the method, path, body hash, time, nonce and the server's fingerprint; and the
server's answer checked against its link key, so a server pretending to be MoolaKata gets
nothing past the connector."""

import hashlib
import os
import time

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from .keys import b64, unb64

SKEW = 60


class Refused(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _lines(*parts) -> bytes:
    return "\n".join(str(p) for p in parts).encode()


def body_hash(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def sign(key: Ed25519PrivateKey, method: str, path: str, body: bytes, server_fp: str):
    """The headers of a signed call, and its nonce for checking the answer, which names it."""
    t = str(int(time.time()))
    nonce = b64(os.urandom(16))
    msg = _lines("MK-CONN-1", method.upper(), path, body_hash(body), t, nonce, server_fp)
    headers = {
        "MK-Conn-Key": b64(key.public_key().public_bytes_raw()),
        "MK-Conn-Time": t,
        "MK-Conn-Nonce": nonce,
        "MK-Conn-Signature": b64(key.sign(msg)),
    }
    return headers, nonce


def verify_answer(
    server_public: bytes,
    status: int,
    body: bytes,
    nonce: str,
    headers,
    own_fp: str,
    call_hash: str,
) -> None:
    """The answer signed by the server, to this connector and this call (protocol §3.3), so a
    server's answer to another caller or another request is refused."""
    h = {k.lower(): v for k, v in dict(headers).items()}
    try:
        t = int(h["mk-conn-time"])
        sig = unb64(h["mk-conn-signature"])
    except KeyError, ValueError:
        raise Refused("answer-unsigned", "The server's answer wasn't signed.") from None
    if abs(time.time() - t) > SKEW:
        raise Refused("clock-skew", "The server's clock is more than a minute off.")
    try:
        Ed25519PublicKey.from_public_bytes(server_public).verify(
            sig,
            _lines("MK-CONN-1-ANSWER", status, body_hash(body), t, nonce, own_fp, call_hash),
        )
    except InvalidSignature:
        raise Refused(
            "bad-signature", "The answer isn't signed by the server paired with."
        ) from None
