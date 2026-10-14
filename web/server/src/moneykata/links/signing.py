"""Signed calls between linked servers (requirements S11.1.3, docs/link-protocol.md).

A request carries four headers: `MK-Link-Key` (the sender's public key), `MK-Link-Time`
(Unix seconds), `MK-Link-Nonce` (16 random bytes) and `MK-Link-Signature`, an Ed25519 signature
over these lines:

    MK-LINK-1
    <method>
    <path, with its query>
    <SHA-256 of the body, hex>
    <time>
    <nonce>
    <the receiver's fingerprint>

The receiver refuses a key it has no link with, a bad signature, a time more than 60 seconds
off its own, and a nonce it has seen in the last two minutes. The answer is signed the same
way (`MK-LINK-1-ANSWER`, the status in place of the method and path, and the request's nonce),
so the caller knows who answered."""

import hashlib
import secrets
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from .keys import b64, fingerprint, raw_public, unb64

SKEW = 60  # seconds a call's time may be off
NONCE_SECONDS = 120


class Refused(Exception):
    """A call that isn't from a linked server, or not now."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _lines(*parts) -> bytes:
    return "\n".join(str(p) for p in parts).encode()


def body_hash(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


@dataclass(frozen=True)
class Signed:
    headers: dict[str, str]
    nonce: str


def sign_request(
    key: Ed25519PrivateKey, method: str, path: str, body: bytes, receiver_fp: str, now=None
) -> Signed:
    t = str(int(now if now is not None else time.time()))
    nonce = b64(secrets.token_bytes(16))
    msg = _lines("MK-LINK-1", method.upper(), path, body_hash(body), t, nonce, receiver_fp)
    return Signed(
        {
            "MK-Link-Key": b64(raw_public(key.public_key())),
            "MK-Link-Time": t,
            "MK-Link-Nonce": nonce,
            "MK-Link-Signature": b64(key.sign(msg)),
        },
        nonce,
    )


def sign_answer(key: Ed25519PrivateKey, status: int, body: bytes, nonce: str, now=None) -> dict:
    t = str(int(now if now is not None else time.time()))
    msg = _lines("MK-LINK-1-ANSWER", status, body_hash(body), t, nonce)
    return {"MK-Link-Time": t, "MK-Link-Signature": b64(key.sign(msg))}


def verify_answer(public: bytes, status: int, body: bytes, nonce: str, headers, now=None) -> None:
    try:
        t = int(headers["MK-Link-Time"])
        sig = unb64(headers["MK-Link-Signature"])
    except (KeyError, ValueError):
        raise Refused("answer-unsigned", "The linked server's answer wasn't signed.") from None
    if abs((now if now is not None else time.time()) - t) > SKEW:
        raise Refused("clock-skew", "The linked server's clock is more than a minute off.")
    try:
        Ed25519PublicKey.from_public_bytes(public).verify(
            sig, _lines("MK-LINK-1-ANSWER", status, body_hash(body), t, nonce)
        )
    except InvalidSignature:
        raise Refused("bad-signature", "The answer isn't signed by the linked server.") from None


class Nonces:
    """Nonces seen in the last two minutes, per key: a replay is refused."""

    def __init__(self, clock: Callable[[], float] = time.time):
        self._seen: OrderedDict[tuple[str, str], float] = OrderedDict()
        self._lock = threading.Lock()
        self._clock = clock

    def first(self, key: str, nonce: str) -> bool:
        now = self._clock()
        with self._lock:
            while self._seen and next(iter(self._seen.values())) < now - NONCE_SECONDS:
                self._seen.popitem(last=False)
            if (key, nonce) in self._seen:
                return False
            self._seen[(key, nonce)] = now
            return True


@dataclass(frozen=True)
class Caller:
    public: bytes
    nonce: str


def verify_request(
    headers, method: str, path: str, body: bytes, own_fp: str, nonces: Nonces, now=None
) -> Caller:
    """The verified caller's key, or Refused. Which link it belongs to is the caller's check."""
    try:
        public = unb64(headers["mk-link-key"])
        t = int(headers["mk-link-time"])
        nonce = headers["mk-link-nonce"]
        sig = unb64(headers["mk-link-signature"])
    except (KeyError, ValueError):
        raise Refused("unsigned", "A linked server's call must be signed.") from None
    if len(public) != 32 or not 8 <= len(nonce) <= 64:
        raise Refused("unsigned", "A linked server's call must be signed.")
    if abs((now if now is not None else time.time()) - t) > SKEW:
        raise Refused("clock-skew", "The call's time is more than a minute off this server's.")
    msg = _lines("MK-LINK-1", method.upper(), path, body_hash(body), t, nonce, own_fp)
    try:
        Ed25519PublicKey.from_public_bytes(public).verify(sig, msg)
    except (InvalidSignature, ValueError):
        raise Refused("bad-signature", "The call's signature doesn't match its key.") from None
    if not nonces.first(fingerprint(public), nonce):
        raise Refused("replayed", "This call was already made.")
    return Caller(public, nonce)
