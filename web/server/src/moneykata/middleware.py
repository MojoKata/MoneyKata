"""What every request passes through (requirements S13.7): the client's real address, the
response headers, the Origin check on changes, and the size of request bodies.

Plain ASGI middleware, so streaming responses (the live stream, receipt files) pass straight
through.
"""

import ipaddress
import json
import logging
import time
from collections.abc import Callable

from .errors import new_error_id

log = logging.getLogger("moneykata.access")

APP_CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; "
    "connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'none'; "
    "form-action 'self'; frame-ancestors 'none'"
)

COMMON_HEADERS = [
    (b"x-content-type-options", b"nosniff"),
    (b"referrer-policy", b"no-referrer"),
    (b"cross-origin-opener-policy", b"same-origin"),
    (b"cross-origin-resource-policy", b"same-origin"),
    (b"permissions-policy", b"camera=(), microphone=(), geolocation=(), payment=()"),
]
HSTS = (b"strict-transport-security", b"max-age=31536000")

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
JSON_LIMIT = 1024 * 1024


def _send_problem(status: int, code: str, detail: str, headers=()):
    body = json.dumps(
        {
            "type": f"https://moneykata.invalid/problems/{code}",
            "title": {403: "Not allowed", 413: "Too large"}.get(status, "Error"),
            "status": status,
            "detail": detail,
            "code": code,
            "errorId": new_error_id(),
            "errors": [],
        }
    ).encode()

    async def respond(send):
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [
                    (b"content-type", b"application/problem+json"),
                    (b"content-length", str(len(body)).encode()),
                    *headers,
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})

    return respond


class ClientAddress:
    """In proxy mode, believe X-Forwarded-For and -Proto only from the configured proxies; in
    tls mode, ignore them (S13.3)."""

    def __init__(self, app, mode: str, trusted: tuple):
        self.app = app
        self.mode = mode
        self.trusted = trusted

    def _is_trusted(self, host: str) -> bool:
        try:
            addr = ipaddress.ip_address(host)
        except ValueError:
            return False
        return any(addr in net for net in self.trusted)

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket") and self.mode == "proxy" and scope.get("client"):
            peer = scope["client"][0]
            if self._is_trusted(peer):
                headers = {k.lower(): v.decode("latin-1") for k, v in scope["headers"]}
                chain = [
                    h.strip() for h in headers.get(b"x-forwarded-for", "").split(",") if h.strip()
                ]
                client = peer
                for hop in reversed(chain):
                    client = hop
                    if not self._is_trusted(hop):
                        break
                proto = headers.get(b"x-forwarded-proto", "").split(",")[0].strip()
                scope = dict(scope)
                scope["client"] = (client, 0)
                if proto in ("http", "https"):
                    scope["scheme"] = proto
                forwarded_host = headers.get(b"x-forwarded-host", "").split(",")[0].strip()
                if forwarded_host:
                    scope["headers"] = [(k, v) for k, v in scope["headers"] if k.lower() != b"host"]
                    scope["headers"].append((b"host", forwarded_host.encode("latin-1")))
        await self.app(scope, receive, send)


class SecurityHeaders:
    """The headers of S13.7.7 on every response. A route that needs another CSP (the app's
    page with its nonce, the demo, a receipt file) sets its own, which is kept."""

    def __init__(self, app, tls: bool):
        self.app = app
        self.tls = tls

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def wrapped(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                names = {k.lower() for k, _ in headers}
                if b"content-security-policy" not in names:
                    headers.append((b"content-security-policy", APP_CSP.encode()))
                headers.extend(h for h in COMMON_HEADERS if h[0] not in names)
                if self.tls:
                    headers.append(HSTS)
                message = dict(message, headers=headers)
            await send(message)

        await self.app(scope, receive, wrapped)


class OriginCheck:
    """A request that changes something must come from the app's own origin (S13.7.4)."""

    def __init__(self, app, prefixes=("/ui/",)):
        self.app = app
        self.prefixes = prefixes

    async def __call__(self, scope, receive, send):
        if (
            scope["type"] == "http"
            and scope["method"] not in SAFE_METHODS
            and scope["path"].startswith(self.prefixes)
        ):
            headers = {k.lower(): v.decode("latin-1") for k, v in scope["headers"]}
            origin = headers.get(b"origin")
            host = headers.get(b"host", "")
            expected = f"{scope.get('scheme', 'http')}://{host}"
            if not origin or origin != expected:
                await _send_problem(
                    403, "origin-refused", "This request did not come from MoneyKata's own page."
                )(send)
                return
        await self.app(scope, receive, send)


class BodyLimit:
    """JSON bodies up to 1 MB; uploads (multipart) up to the size Settings allow (S13.7.6)."""

    def __init__(self, app, upload_limit: Callable[[], int]):
        self.app = app
        self.upload_limit = upload_limit

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] in SAFE_METHODS:
            await self.app(scope, receive, send)
            return
        headers = {k.lower(): v.decode("latin-1") for k, v in scope["headers"]}
        ctype = headers.get(b"content-type", "")
        limit = self.upload_limit() if ctype.startswith("multipart/") else JSON_LIMIT
        too_large = _send_problem(
            413, "too-large", f"The request is larger than {limit // (1024 * 1024)} MB."
        )
        length = headers.get(b"content-length")
        if length and length.isdigit() and int(length) > limit:
            await too_large(send)
            return
        seen = 0
        started = False

        async def counted():
            nonlocal seen
            message = await receive()
            if message["type"] == "http.request":
                seen += len(message.get("body", b""))
                if seen > limit:
                    raise _TooLarge
            return message

        async def tracking(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, counted, tracking)
        except _TooLarge:
            if not started:
                await too_large(send)


class _TooLarge(Exception):
    pass


class AccessLog:
    """One line per request: method, path, status, time. Never a query string, body or
    cookie, which could carry names or amounts (S13.7.9)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        start = time.monotonic()
        status = 0

        async def wrapped(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, wrapped)
        finally:
            user = scope.get("state", {}).get("user_id", "-")
            log.info(
                "%s %s %s %s %.0fms",
                scope["method"],
                scope["path"],
                status,
                user,
                (time.monotonic() - start) * 1000,
            )


class SessionCookie:
    """Writes the session cookie a route or dependency asked for (request.state.set_cookie):
    HttpOnly, Secure, SameSite=Strict, Path=/ui (S13.7.1). An empty value clears it."""

    def __init__(self, app, max_age: Callable[[], int]):
        self.app = app
        self.max_age = max_age

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def wrapped(message):
            if message["type"] == "http.response.start":
                token = scope.get("state", {}).get("set_cookie")
                if token is not None:
                    if token:
                        cookie = (
                            f"mk_session={token}; Path=/ui; Max-Age={self.max_age()}; "
                            "HttpOnly; Secure; SameSite=Strict"
                        )
                    else:
                        cookie = (
                            "mk_session=; Path=/ui; Max-Age=0; HttpOnly; Secure; SameSite=Strict"
                        )
                    message = dict(
                        message,
                        headers=[*message.get("headers", []), (b"set-cookie", cookie.encode())],
                    )
            await send(message)

        await self.app(scope, receive, wrapped)
