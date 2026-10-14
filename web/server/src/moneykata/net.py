"""Outbound calls (requirements S13.5): one httpx client behind an egress guard. Only the hosts
of enabled price sources, the bitcoin explorer or node, and links are reached; never loopback,
link-local or cloud metadata addresses unless an admin allows that host by name; with
timeouts and a ceiling on the size of a response."""

import ipaddress
import socket
import threading
from collections.abc import Callable, Iterable

import httpx

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

    def check(self, host: str, port: int) -> None:
        host = host.lower().rstrip(".")
        with self._lock:
            allowed, named = host in self._hosts, host in self._named
        if not allowed:
            raise EgressRefused(f"{host} is not a host MoneyKata is set up to reach")
        if named:
            return
        try:
            addrs = [ipaddress.ip_address(host)]
        except ValueError:
            try:
                addrs = [ipaddress.ip_address(a.split("%")[0]) for a in self._resolver(host, port)]
            except OSError as e:
                raise httpx.ConnectError(f"cannot resolve {host}: {e}") from None
        for a in addrs:
            why = _forbidden(a)
            if why:
                raise EgressRefused(f"{host} resolves to {why}; an admin can allow it by name")


class _Transport(httpx.HTTPTransport):
    def __init__(self, guard: Guard, max_bytes: int, **kw) -> None:
        super().__init__(**kw)
        self._guard = guard
        self._max = max_bytes

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        url = request.url
        port = url.port or (443 if url.scheme == "https" else 80)
        if url.scheme not in ("https", "http"):
            raise EgressRefused(f"{url.scheme} is not allowed")
        self._guard.check(url.host, port)
        response = super().handle_request(request)
        length = response.headers.get("content-length")
        if length and length.isdigit() and int(length) > self._max:
            response.close()
            raise ResponseTooLarge(f"the response from {url.host} is larger than allowed")
        return response


class Client(httpx.Client):
    """httpx.Client with the guard, the timeouts and a ceiling on the bytes read."""

    def __init__(self, guard: Guard, max_bytes: int = MAX_RESPONSE, **kw) -> None:
        super().__init__(
            transport=_Transport(guard, max_bytes),
            timeout=TIMEOUT,
            follow_redirects=False,
            headers={"User-Agent": "MoneyKata"},
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
