"""Calling a linked server (requirements S11.1.3, S11.2): signed requests over HTTPS through
the egress guard, and their signed answers checked."""

import json

from .. import exactjson, net
from . import PROTOCOL, keys, signing


class LinkError(Exception):
    """The linked server couldn't be reached, or refused: the message says which."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _url(address: str, path: str) -> str:
    return address.rstrip("/") + path


def hello(srv, address: str) -> dict:
    """The unsigned hello: the peer's protocol, version and fingerprint."""
    try:
        r = net.Client(srv.guard, verify=False).get(_url(address, "/link/v1/hello"))
    except net.httpx.HTTPError as e:
        raise LinkError("unreachable", f"{address} didn't answer ({type(e).__name__}).") from None
    if r.status_code != 200:
        raise LinkError("not-moneykata", f"{address} doesn't answer as a MoneyKata server.")
    return r.json()


def call(srv, address: str, peer_key: bytes, path: str, data: dict | None = None) -> dict:
    """A signed POST to the peer, its answer checked against the peer's key."""
    with srv.db.tx() as s:
        own = keys.private_key(s, srv.keys.secrets)
    body = exactjson.dumps(data or {}, separators=(",", ":")).encode()
    signed = signing.sign_request(own, "POST", path, body, keys.fingerprint(peer_key))
    headers = {
        **signed.headers,
        "Content-Type": "application/json",
        "MK-Link-Protocol": str(PROTOCOL),
        "MK-Link-Version": srv.version,
    }
    try:
        # A peer's certificate is often its own (S13.3): what proves who answered is the
        # signature on the answer, checked against the key the link was made with.
        r = net.Client(srv.guard, verify=False).post(
            _url(address, path), content=body, headers=headers
        )
    except net.httpx.HTTPError as e:
        raise LinkError("unreachable", f"{address} didn't answer ({type(e).__name__}).") from None
    try:
        signing.verify_answer(peer_key, r.status_code, r.content, signed.nonce, r.headers)
    except signing.Refused as e:
        raise LinkError(e.code, e.message) from None
    out = exactjson.loads(r.content) if r.content else {}
    if r.status_code >= 400:
        raise LinkError(
            out.get("code", "refused"), out.get("message", f"refused ({r.status_code})")
        )
    return out


def iter_file(srv, address: str, peer_key: bytes, file_id: str, digest_out: list):
    """One receipt's bytes from the peer, piece by piece as they arrive. When the stream ends,
    the peer's signature over their SHA-256 is checked, and the digest appended to
    `digest_out`; a bad one raises before the last piece is taken as good."""
    import hashlib

    with srv.db.tx() as s:
        own = keys.private_key(s, srv.keys.secrets)
    path = "/link/v1/file"
    body = json.dumps({"id": file_id}, separators=(",", ":")).encode()
    signed = signing.sign_request(own, "POST", path, body, keys.fingerprint(peer_key))
    headers = {
        **signed.headers,
        "Content-Type": "application/json",
        "MK-Link-Protocol": str(PROTOCOL),
        "MK-Link-Version": srv.version,
    }
    h = hashlib.sha256()
    try:
        c = net.Client(srv.guard, verify=False)
        with c.stream("POST", _url(address, path), content=body, headers=headers) as r:
            if r.status_code != 200:
                r.read()
                raise LinkError("file-refused", f"The file was refused ({r.status_code}).")
            for piece in r.iter_bytes():
                h.update(piece)
                yield piece
            answer_headers = r.headers
    except net.httpx.HTTPError as e:
        raise LinkError("unreachable", f"{address} didn't answer ({type(e).__name__}).") from None
    digest = h.hexdigest()
    try:
        signing.verify_answer(peer_key, 200, b"", signed.nonce, answer_headers, digest=digest)
    except signing.Refused as e:
        raise LinkError(e.code, e.message) from None
    digest_out.append(digest)
