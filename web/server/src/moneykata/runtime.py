"""Starting and stopping the server: everything that happens before the first request and
after the last."""

import asyncio
import datetime as dt
import logging

from sqlalchemy import select

from . import listener, settings, timezones
from .app import Server, create_app
from .config import Config
from .store import maintenance
from .store.entities.core import TaskRun
from .tasks import Daily, TaskContext
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

    return record


def last_runs(server: Server) -> dict[str, Run]:
    with server.db.read() as s:
        return {r.name: Run(r.startedAt, r.finishedAt, r.error) for r in s.scalars(select(TaskRun))}


def register_tasks(server: Server) -> None:
    """The background tasks of §16.4 that this release has."""
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


def build(config: Config) -> Server:
    store = maintenance.open_store(config)
    server = Server(config=config, store=store)
    register_tasks(server)
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
