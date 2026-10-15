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
so the caller knows who answered.

The MoneyKata Connector signs its calls the same way under its own scheme (`MK-Conn-*`
headers, `MK-CONN-1` labels; docs/connector-protocol.md §3): the `scheme` argument picks
which."""

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


@dataclass(frozen=True)
class Scheme:
    """The header prefix and the signed text's first line of one kind of signed call."""

    header: str  # MK-<header>-Key, -Time, -Nonce, -Signature
    label: str  # the first line: MK-LINK-1, MK-CONN-1

    def h(self, name: str) -> str:
        return f"MK-{self.header}-{name}"

    def lower(self, name: str) -> str:
        return self.h(name).lower()


LINK = Scheme("Link", "MK-LINK-1")
CONN = Scheme("Conn", "MK-CONN-1")


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
    key: Ed25519PrivateKey,
    method: str,
    path: str,
    body: bytes,
    receiver_fp: str,
    now=None,
    scheme: Scheme = LINK,
) -> Signed:
    t = str(int(now if now is not None else time.time()))
    nonce = b64(secrets.token_bytes(16))
    msg = _lines(scheme.label, method.upper(), path, body_hash(body), t, nonce, receiver_fp)
    return Signed(
        {
            scheme.h("Key"): b64(raw_public(key.public_key())),
            scheme.h("Time"): t,
            scheme.h("Nonce"): nonce,
            scheme.h("Signature"): b64(key.sign(msg)),
        },
        nonce,
    )


def sign_answer(
    key: Ed25519PrivateKey,
    status: int,
    body: bytes,
    nonce: str,
    now=None,
    digest=None,
    scheme: Scheme = LINK,
) -> dict:
    """`digest` signs a body streamed later, by its SHA-256, rather than bytes in hand."""
    t = str(int(now if now is not None else time.time()))
    msg = _lines(scheme.label + "-ANSWER", status, digest or body_hash(body), t, nonce)
    return {scheme.h("Time"): t, scheme.h("Signature"): b64(key.sign(msg))}


def verify_answer(
    public: bytes,
    status: int,
    body: bytes,
    nonce: str,
    headers,
    now=None,
    digest=None,
    scheme: Scheme = LINK,
) -> None:
    who = "linked server" if scheme is LINK else "server"
    try:
        t = int(headers[scheme.h("Time")])
        sig = unb64(headers[scheme.h("Signature")])
    except KeyError, ValueError:
        raise Refused("answer-unsigned", f"The {who}'s answer wasn't signed.") from None
    if abs((now if now is not None else time.time()) - t) > SKEW:
        raise Refused("clock-skew", f"The {who}'s clock is more than a minute off.")
    try:
        Ed25519PublicKey.from_public_bytes(public).verify(
            sig, _lines(scheme.label + "-ANSWER", status, digest or body_hash(body), t, nonce)
        )
    except InvalidSignature:
        raise Refused("bad-signature", f"The answer isn't signed by the {who}.") from None


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
    headers,
    method: str,
    path: str,
    body: bytes,
    own_fp: str,
    nonces: Nonces,
    now=None,
    scheme: Scheme = LINK,
) -> Caller:
    """The verified caller's key, or Refused. Which link (or connector) it belongs to is the
    caller's check."""
    who = "A linked server's" if scheme is LINK else "The connector's"
    try:
        public = unb64(headers[scheme.lower("key")])
        t = int(headers[scheme.lower("time")])
        nonce = headers[scheme.lower("nonce")]
        sig = unb64(headers[scheme.lower("signature")])
    except KeyError, ValueError:
        raise Refused("unsigned", f"{who} call must be signed.") from None
    if len(public) != 32 or not 8 <= len(nonce) <= 64:
        raise Refused("unsigned", f"{who} call must be signed.")
    if abs((now if now is not None else time.time()) - t) > SKEW:
        raise Refused("clock-skew", "The call's time is more than a minute off this server's.")
    msg = _lines(scheme.label, method.upper(), path, body_hash(body), t, nonce, own_fp)
    try:
        Ed25519PublicKey.from_public_bytes(public).verify(sig, msg)
    except InvalidSignature, ValueError:
        raise Refused("bad-signature", "The call's signature doesn't match its key.") from None
    if not nonces.first(fingerprint(public), nonce):
        raise Refused("replayed", "This call was already made.")
    return Caller(public, nonce)
