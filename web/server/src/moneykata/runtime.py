"""Starting and stopping the server: everything that happens before the first request and
after the last."""

import asyncio
import datetime as dt
import logging

from sqlalchemy import delete, select

from . import figures, listener, settings, timezones
from .app import Server, create_app
from .auth import sessions, users
from .config import Config
from .prices import refresh as pricing
from .store import maintenance
from .store.entities.core import TaskRun
from .store.entities.users import OneTimeToken
from .store.repos import ledger
from .tasks import Daily, Every, TaskContext
from .tasks import TaskRun as Run

log = logging.getLogger("moneykata")


def record_run(server: Server):
    def record(name: str, run: Run) -> None:
        with server.db.tx() as s:
            row = s.get(TaskRun, name)
            if row is None:
                s.add(
                    TaskRun(
                        name=name, startedAt=run.started, finishedAt=run.finished, error=run.error
                    )
                )
            else:
                row.startedAt, row.finishedAt, row.error = run.started, run.finished, run.error
        # Its name only: Settings › Backups and Key storage reload when theirs ends.
        server.events.publish("task", {"name": name})

    return record


def last_runs(server: Server) -> dict[str, Run]:
    with server.db.read() as s:
        return {r.name: Run(r.startedAt, r.finishedAt, r.error) for r in s.scalars(select(TaskRun))}


def register_tasks(server: Server) -> None:
    """The background tasks of S13.4 that this release has."""
    from .tasks import Tasks

    server.tasks = Tasks(record=record_run(server))
    last = last_runs(server)

    def setting_time(key: str):
        def at() -> tuple[dt.time, str]:
            with server.db.read() as s:
                return settings.time_of(s, key), timezones.host_zone()

        return at

    def backup(ctx: TaskContext) -> None:
        maintenance.backup(server.config, server.store)
        with server.db.read() as s:
            keep = settings.get(s, "backupCopies")
        maintenance.prune(server.config, keep)

    server.tasks.register("backups", backup, Daily(setting_time("backupTime")), last.get("backups"))

    def prune(ctx: TaskContext) -> None:
        """Expired sessions and one-time tokens are removed outright (schema.md §4.4.1)."""
        with server.db.tx() as s:
            sessions.prune(s)
            s.execute(delete(OneTimeToken).where(OneTimeToken.expiresAt <= sessions.now()))

    server.tasks.register("pruning", prune, Every(3600), last.get("pruning"))

    def price_time() -> tuple[dt.time, str]:
        with server.db.read() as s:
            return settings.time_of(s, "priceRefreshTime"), settings.get(s, "priceRefreshZone")

    server.tasks.register(
        "prices", lambda ctx: pricing.refresh(server, ctx), Daily(price_time), last.get("prices")
    )

    def reencrypt(ctx: TaskContext) -> None:
        """Settings › Key storage › Re-encrypt: only when asked (S15.7.2)."""
        server.store = maintenance.reencrypt(server.config, server.store)
        with server.db.tx() as s:
            from . import activity

            activity.record(s, "keys.reencrypted", actor=None, for_admins=True)

    server.tasks.register("reencrypt", reencrypt, None, last.get("reencrypt"))


def build(config: Config) -> Server:
    store = maintenance.open_store(config)
    pricing.install()
    server = Server(config=config, store=store)
    with server.db.tx() as s:
        if users.ensure_default_admin(s):
            log.info("made the default admin: sign in as %s to set it up", users.DEFAULT_ADMIN)
        ledger.ensure_categories(s)
        figures.ensure_benchmarks(s)
    if config.dev and config.stubs:
        from .dev import devmode

        devmode.enable_stub_prices(server)
    register_tasks(server)
    from .ui.prices import apply_egress

    apply_egress(server)
    return server


async def start(config: Config, seed: bool = False) -> int:
    if config.dev:
        from .dev import devmode

        devmode.prepare(config)
    server = build(config)
    if config.dev:
        from .dev import devmode

        devmode.after_start(server, seed=seed)
    app = create_app(server)
    server.events.bind(asyncio.get_running_loop())

    async def on_stop() -> None:
        server.ready = False
        await server.events.close_all()
        server.tasks.stop()

    server.tasks.start()
    server.ready = True
    scheme = "https" if config.mode == "tls" else "http"
    log.info(
        "MoneyKata %s%s listening on %s://%s:%s",
        server.version,
        " (dev)" if config.dev else "",
        scheme,
        config.host,
        config.port,
    )
    try:
        await listener.run(app, config, on_stop)
    finally:
        server.db.dispose()
    log.info("stopped")
    return 0
