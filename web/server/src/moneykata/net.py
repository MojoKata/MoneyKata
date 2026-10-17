"""Outbound calls (requirements S13.5): one httpx client behind an egress guard. Only the hosts
of enabled price sources, the bitcoin explorer or node, and links are reached; never loopback,
link-local or cloud metadata addresses unless an admin allows that host by name; with
timeouts and a ceiling on the size of a response, whether or not it announces its length.

Each connection goes to the address the guard checked, never to a second lookup, so a name
can't change its answer in between. TLS is verified before anything is sent: a public
certificate against the system's roots and the name, or, for a server whose certificate is its
own (S11.1.3, S18.4), its key against the fingerprints pinned for it."""

import hashlib
import ipaddress
import socket
import ssl
import threading
from collections.abc import Callable, Iterable

import httpcore
import httpx
from cryptography import x509
from cryptography.hazmat.primitives import serialization

TIMEOUT = httpx.Timeout(20.0, connect=10.0)
MAX_RESPONSE = 20 * 1024 * 1024
METADATA = {
    ipaddress.ip_address("169.254.169.254"),
    ipaddress.ip_address("fd00:ec2::254"),
    ipaddress.ip_address("100.100.100.200"),
}


class EgressRefused(httpx.TransportError):
    pass


class ResponseTooLarge(httpx.TransportError):
    pass


class CertificateRefused(httpx.ConnectError):
    """A pinned server presented a certificate whose key isn't one pinned for it."""

    def __init__(self, fingerprint: str):
        super().__init__(f"the server's certificate key {fingerprint} isn't the one pinned")
        self.fingerprint = fingerprint


def key_fingerprint(der: bytes) -> str:
    """A certificate's key, as pinned: the SHA-256 of its SubjectPublicKeyInfo, in hex."""
    spki = (
        x509.load_der_x509_certificate(der)
        .public_key()
        .public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    )
    return hashlib.sha256(spki).hexdigest()


def _forbidden(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> str | None:
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
        addr = addr.ipv4_mapped
    if addr in METADATA:
        return "a cloud metadata address"
    if addr.is_loopback:
        return "a loopback address"
    if addr.is_link_local:
        return "a link-local address"
    if addr.is_unspecified or addr.is_multicast or addr.is_reserved:
        return "not a host address"
    return None


Resolver = Callable[[str, int], list[str]]


def system_resolver(host: str, port: int) -> list[str]:
    return [info[4][0] for info in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)]


class Guard:
    """Which hosts may be reached. The allowed set is rebuilt when Settings change."""

    def __init__(self, resolver: Resolver = system_resolver) -> None:
        self._lock = threading.Lock()
        self._hosts: set[str] = set()
        self._named: set[str] = set()
        self._resolver = resolver

    def allow(self, hosts: Iterable[str], allowed_by_name: Iterable[str] = ()) -> None:
        """Hosts in use, and those an admin allowed by name to be loopback or link-local
        (a node on this machine)."""
        with self._lock:
            self._hosts = {h.lower().rstrip(".") for h in hosts}
            self._named = {h.lower().rstrip(".") for h in allowed_by_name}

    def snapshot(self) -> tuple[set[str], set[str]]:
        with self._lock:
            return set(self._hosts), set(self._named)

    def check(self, host: str, port: int) -> str:
        """The address to connect to for this host, once it is allowed: every address the name
        resolves to is checked, and the first is the one connected to."""
        host = host.lower().rstrip(".")
        with self._lock:
            allowed, named = host in self._hosts, host in self._named
        if not allowed:
            raise EgressRefused(f"{host} is not a host MoneyKata is set up to reach")
        try:
            addrs = [ipaddress.ip_address(host.strip("[]"))]
        except ValueError:
            try:
                addrs = [ipaddress.ip_address(a.split("%")[0]) for a in self._resolver(host, port)]
            except OSError as e:
                raise httpx.ConnectError(f"cannot resolve {host}: {e}") from None
        if not addrs:
            raise httpx.ConnectError(f"cannot resolve {host}")
        for a in addrs if not named else ():
            why = _forbidden(a)
            if why:
                raise EgressRefused(f"{host} resolves to {why}; an admin can allow it by name")
        return str(addrs[0])


PRESENTED = "moneykata-pinned-key"


def presented(response: httpx.Response) -> str | None:
    """The pinned certificate key a response came over, when the server was pinned."""
    stream = response.extensions.get("network_stream")
    return stream.get_extra_info(PRESENTED) if stream is not None else None


class _Stream(httpcore.NetworkStream):
    """A connection whose TLS, once made, is checked against the pins before it is used."""

    def __init__(
        self, inner: httpcore.NetworkStream, pins: frozenset[str] | None, presented=None
    ) -> None:
        self._inner = inner
        self._pins = pins
        self._presented = presented  # the pinned key this TLS connection came over

    def read(self, max_bytes: int, timeout: float | None = None) -> bytes:
        return self._inner.read(max_bytes, timeout)

    def write(self, buffer: bytes, timeout: float | None = None) -> None:
        self._inner.write(buffer, timeout)

    def close(self) -> None:
        self._inner.close()

    def start_tls(self, ssl_context, server_hostname=None, timeout=None):
        tls = self._inner.start_tls(ssl_context, server_hostname, timeout)
        if self._pins is not None:
            sock = tls.get_extra_info("socket")
            der = sock.getpeercert(binary_form=True) if sock is not None else None
            fp = key_fingerprint(der) if der else ""
            if fp not in self._pins:
                tls.close()
                raise CertificateRefused(fp)
            return _Stream(tls, None, fp)
        return _Stream(tls, None)

    def get_extra_info(self, info: str):
        if info == PRESENTED:
            return self._presented
        return self._inner.get_extra_info(info)


class _Backend(httpcore.SyncBackend):
    def __init__(self, guard: Guard, pins: frozenset[str] | None) -> None:
        self._guard = guard
        self._pins = pins

    def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        address = self._guard.check(host, port)
        stream = super().connect_tcp(address, port, timeout, local_address, socket_options)
        return _Stream(stream, self._pins)


class _Capped(httpx.SyncByteStream):
    """An answer read only up to the ceiling, however it is sent."""

    def __init__(self, inner, max_bytes: int, host: str) -> None:
        self._inner, self._max, self._host = inner, max_bytes, host

    def __iter__(self):
        size = 0
        for chunk in self._inner:
            size += len(chunk)
            if size > self._max:
                raise ResponseTooLarge(f"the response from {self._host} is larger than allowed")
            yield chunk

    def close(self) -> None:
        self._inner.close()


def tls_context(pins: frozenset[str] | None) -> ssl.SSLContext:
    """The system's roots and the name, or, pinned, no chain at all: the key decides."""
    ctx = ssl.create_default_context()
    if pins is not None:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx


class _Transport(httpx.HTTPTransport):
    def __init__(self, guard: Guard, max_bytes: int, pins: frozenset[str] | None) -> None:
        super().__init__()
        # The connection pool connects through the guard, to the address it checked.
        self._pool = httpcore.ConnectionPool(
            ssl_context=tls_context(pins),
            max_connections=10,
            max_keepalive_connections=5,
            keepalive_expiry=5.0,
            network_backend=_Backend(guard, pins),
        )
        self._max = max_bytes

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        url = request.url
        if url.scheme not in ("https", "http"):
            raise EgressRefused(f"{url.scheme} is not allowed")
        response = super().handle_request(request)
        length = response.headers.get("content-length")
        if length and length.isdigit() and int(length) > self._max:
            response.close()
            raise ResponseTooLarge(f"the response from {url.host} is larger than allowed")
        response.stream = _Capped(response.stream, self._max, url.host)
        return response


class Client(httpx.Client):
    """httpx.Client with the guard, the timeouts and a ceiling on the bytes read. `pins`, the
    fingerprints of certificate keys accepted for a server whose certificate is its own, takes
    the place of the system's roots for that server."""

    def __init__(
        self,
        guard: Guard,
        max_bytes: int = MAX_RESPONSE,
        pins: Iterable[str] | None = None,
        **kw,
    ) -> None:
        if "verify" in kw:
            raise TypeError("TLS is always verified: pin a server's own certificate instead")
        headers = {"User-Agent": "MoneyKata", **(kw.pop("headers", None) or {})}
        pinned = frozenset(pins) if pins is not None else None
        super().__init__(
            transport=_Transport(guard, max_bytes, pinned),
            timeout=TIMEOUT,
            follow_redirects=False,
            headers=headers,
            **kw,
        )
        self._max = max_bytes

    def get_bytes(self, url: str, **kw) -> tuple[httpx.Response, bytes]:
        """GET, reading at most the ceiling: a server that sends more is cut off."""
        with self.stream("GET", url, **kw) as r:
            chunks, size = [], 0
            for chunk in r.iter_bytes():
                size += len(chunk)
                if size > self._max:
                    raise ResponseTooLarge("the response is larger than allowed")
                chunks.append(chunk)
            return r, b"".join(chunks)
