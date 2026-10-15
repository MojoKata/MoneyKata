"""Calls out (requirements S18.2.2, S18.1.1): the connector only opens connections, to
MoneyKata and to each driver's declared hosts, through one egress allowlist that refuses any
other host. The standard library's HTTPS client; MoneyKata's own certificate may be
self-signed, so what proves who answered is the signature on the answer (protocol §1.2), and a
driver's institution is checked by its certificate as usual."""

import http.client
import json
import ssl
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from . import PROTOCOL, VERSION, signing
from .keys import Pairing, unb64


class EgressRefused(Exception):
    pass


@dataclass
class Egress:
    """The hosts that may be reached: MoneyKata's, and each driver's declared ones."""

    allowed: set[str] = field(default_factory=set)

    def allow(self, *hosts: str) -> None:
        self.allowed |= {h.lower() for h in hosts if h}

    def check(self, host: str) -> None:
        if host.lower() not in self.allowed:
            raise EgressRefused(f"{host} is not a host this connector may reach")


@dataclass
class Answer:
    status: int
    headers: dict
    body: bytes

    def json(self) -> dict:
        return json.loads(self.body) if self.body else {}


class Transport:
    """One HTTPS request; `verify` False for MoneyKata (its answer is signed instead)."""

    def __init__(self, egress: Egress):
        self.egress = egress

    def request(self, method: str, url: str, headers: dict, body: bytes, verify=True) -> Answer:
        u = urlsplit(url)
        host = u.hostname or ""
        self.egress.check(host)
        ctx = ssl.create_default_context()
        if not verify:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        conn_cls = (
            http.client.HTTPSConnection if u.scheme == "https" else http.client.HTTPConnection
        )
        kw = {"context": ctx} if u.scheme == "https" else {}
        conn = conn_cls(host, u.port, timeout=60, **kw)
        try:
            path = u.path + (f"?{u.query}" if u.query else "")
            conn.request(method, path, body=body, headers=headers)
            r = conn.getresponse()
            return Answer(r.status, {k: v for k, v in r.getheaders()}, r.read())
        finally:
            conn.close()


class ServerError(Exception):
    def __init__(self, code: str, message: str, status: int = 0, retry_after: int = 0):
        super().__init__(message)
        self.code, self.message, self.status, self.retry_after = code, message, status, retry_after


class Server:
    """MoneyKata, as the connector calls it: signed calls, signed answers."""

    def __init__(self, pairing: Pairing, transport: Transport, server_public: bytes):
        self.pairing = pairing
        self.transport = transport
        self.server_public = server_public

    def call(self, path: str, data: dict | None = None, body: bytes | None = None, ctype=None):
        payload = body if body is not None else json.dumps(data or {}).encode()
        headers, nonce = signing.sign(
            self.pairing.identity, "POST", path, payload, self.pairing.server_fp
        )
        headers |= {
            "Content-Type": ctype or "application/json",
            "MK-Conn-Protocol": str(PROTOCOL),
            "MK-Conn-Version": VERSION,
        }
        r = self.transport.request(
            "POST", self.pairing.address.rstrip("/") + path, headers, payload, verify=False
        )
        signing.verify_answer(self.server_public, r.status, r.body, nonce, r.headers)
        out = r.json()
        if r.status >= 400:
            retry = r.headers.get("Retry-After") or r.headers.get("retry-after") or "0"
            raise ServerError(
                out.get("code", "refused"),
                out.get("message", f"refused ({r.status})"),
                r.status,
                int(retry) if retry.isdigit() else 0,
            )
        return out


def hello(transport: Transport, address: str) -> dict:
    r = transport.request("GET", address.rstrip("/") + "/connector/v1/hello", {}, b"", verify=False)
    if r.status != 200:
        raise ServerError("not-moneykata", f"{address} doesn't answer as a MoneyKata server.")
    return r.json()


def server_key(hello_answer: dict) -> bytes:
    return unb64(hello_answer["key"])
