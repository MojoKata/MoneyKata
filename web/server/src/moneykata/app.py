"""The ASGI application: routes, middleware and the server's run-time state."""

import logging
from dataclasses import dataclass, field

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from . import errors, middleware, net, paths, ratelimit, settings, static
from .auth.users import Services
from .config import Config
from .events import STREAM_SECONDS, Broker
from .jobs import Jobs
from .mail import Mailer
from .store.maintenance import Store
from .tasks import Tasks
from .ui.conventions import Idempotency

log = logging.getLogger("moneykata")


@dataclass
class Server:
    """Everything a request may reach, built once at start (main.py) and kept on app.state."""

    config: Config
    store: Store | None = None
    version: str = field(default_factory=paths.version)
    ready: bool = False
    upload_limit: int = 25 * 1024 * 1024
    # The receipt reader (S9.8.4), started with the server; tests run without one.
    reader: object | None = None
    stream_seconds: float = STREAM_SECONDS
    events: Broker = field(default_factory=Broker)
    tasks: Tasks = field(default_factory=Tasks)
    jobs: Jobs = field(default_factory=Jobs)
    idempotency: Idempotency = field(default_factory=Idempotency)
    guard: net.Guard = field(default_factory=net.Guard)
    api_limit: ratelimit.Window = field(default_factory=lambda: ratelimit.Window(600, 60))
    upload_rate: ratelimit.Window = field(default_factory=lambda: ratelimit.Window(60, 3600))
    sign_in: ratelimit.SignInGuard = field(default_factory=ratelimit.SignInGuard)

    def __post_init__(self) -> None:
        self.jobs = Jobs(
            announce=lambda job: self.events.publish(
                "job", {"id": job.id, "state": job.state}, users=[job.userId]
            )
        )
        self.services = Services(self.config, Mailer(self.config))

    def badges(self, caller) -> dict[str, int]:
        """The navigation's counts (S12.1.1), sent on the live stream; they grow with the
        screens that have them. Keys are the entries' labels, lowercased."""
        counts: dict[str, int] = {}
        if self.store is None:
            return counts
        from . import alerts
        from .auth import signup

        with self.db.read() as s:
            unseen = alerts.unseen(s, caller.id, caller.admin)
            waiting = len(signup.waiting(s)) if caller.admin else 0
        if unseen:
            counts["alerts"] = unseen
        if waiting:
            counts["users and groups"] = waiting
        return counts

    def upload_cap(self) -> int:
        """The largest upload a request may carry: the larger of the import and receipt size
        limits in Settings (S13.7.6)."""
        if self.store is None:
            return self.upload_limit
        with self.db.read() as s:
            mb = max(settings.get(s, "importMaxMb"), settings.get(s, "receiptMaxMb"))
        # A file of the limit, with the form around it.
        return (mb + 1) * 1024 * 1024

    def session_max_age(self) -> int:
        if self.store is None:
            return 30 * 86400
        with self.db.read() as s:
            return settings.get(s, "sessionAbsoluteDays") * 86400

    @property
    def db(self):
        assert self.store is not None, "this server was made without a database"
        return self.store.db

    @property
    def keys(self):
        assert self.store is not None
        return self.store.keys.keys

    def http(self) -> net.Client:
        """A client for outbound calls, behind the egress guard (S13.5)."""
        return net.Client(self.guard)


def create_app(server: Server) -> FastAPI:
    app = FastAPI(
        title="MoneyKata",
        version=server.version,
        openapi_url=None,
        docs_url=None,
        redoc_url=None,
    )
    app.state.server = server
    errors.install(app)

    @app.get("/healthz", include_in_schema=False)
    def healthz():
        status = 200 if server.ready else 503
        return JSONResponse(
            {"status": "ok" if server.ready else "starting", "version": server.version},
            status_code=status,
            headers={"Cache-Control": "no-store"},
        )

    from .ui import (
        accounts,
        activity,
        alerts,
        budgets,
        dashboard,
        imports,
        loans,
        portfolios,
        prices,
        profile,
        projections,
        receipts,
        session,
        sharing,
        transactions,
        users,
    )
    from .ui import settings as settings_routes

    for module in (
        session,
        users,
        profile,
        settings_routes,
        accounts,
        transactions,
        imports,
        prices,
        sharing,
        portfolios,
        activity,
        alerts,
        budgets,
        receipts,
        projections,
        loans,
        dashboard,
    ):
        app.include_router(module.router)
    # Last: its catch-alls answer for paths no route above has.
    app.include_router(static.router(static.Static(server.version, server.config.dev)))

    # The last added runs first: the client's address, then the log, the headers, the Origin
    # check and the body limit.
    app.add_middleware(middleware.SessionCookie, max_age=server.session_max_age)
    app.add_middleware(middleware.BodyLimit, upload_limit=server.upload_cap)
    app.add_middleware(middleware.OriginCheck)
    app.add_middleware(middleware.SecurityHeaders, tls=server.config.mode == "tls")
    app.add_middleware(middleware.AccessLog)
    app.add_middleware(
        middleware.ClientAddress, mode=server.config.mode, trusted=server.config.trusted_proxies
    )
    return app
