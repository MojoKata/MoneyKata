"""Starting and stopping the server: everything that happens before the first request and
after the last."""

import asyncio
import datetime as dt
import logging

from sqlalchemy import delete, select

from . import clock, figures, listener, settings, timezones
from .app import Server, create_app
from .auth import sessions, users
from .config import Config, RefuseStart
from .prices import refresh as pricing
from .store import maintenance
from .store.entities.core import TaskRun
from .store.entities.users import OneTimeToken
from .store.repos import ledger
from .tasks import Daily, Every, TaskContext, TaskError
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
        if name not in ("alerts", "alert-summaries"):
            # A task's outcome can open or resolve an alert: look now, not in 15 minutes.
            server.tasks.run_now("alerts")

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
        # Never beside a re-encryption (S15.7.2): one would copy a keyring the other is
        # replacing. The lock makes one wait for the other.
        with server.maintenance_lock:
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
        """Settings › Key storage › Re-encrypt: only when asked, with the phrase (S15.7.2). A
        verified backup first, under the old key, so a failure part-way leaves a known-good
        copy; then the main job and the copies' choices, with backups kept out meanwhile."""
        key, server.reencrypt_key = server.reencrypt_key, None
        choices, server.reencrypt_copies = server.reencrypt_copies, {}
        if key is None:
            raise TaskError("re-encryption needs the recovery phrase: start it from Settings")
        with server.maintenance_lock:
            maintenance.backup(server.config, server.store)
            with server.db.read() as s:
                keep = settings.get(s, "backupCopies")
            maintenance.prune(server.config, keep)
            server.store = maintenance.reencrypt(server.config, server.store, key, choices)
        with server.db.tx() as s:
            from . import activity

            activity.record(s, "keys.reencrypted", actor=None, for_admins=True)

    server.tasks.register("reencrypt", reencrypt, None, last.get("reencrypt"))

    def mail(ctx: TaskContext) -> None:
        """Send what the outbox holds (S16.2): at once when an email is queued, and every five
        minutes for what could not go."""
        from .mail import expire_written, smtp_settings

        expire_written(server.config)
        if not server.services.mailer.waiting():
            return
        with server.db.read() as s:
            smtp = smtp_settings(s, server.keys.secrets)
        server.services.mailer.send_waiting(smtp, server.guard, ctx.stop)

    server.tasks.register("mail", mail, Every(300), last.get("mail"))

    def expire_options(ctx: TaskContext) -> None:
        """Options that expired out of the money end the day after (S3.6)."""
        from . import options

        with server.db.tx() as s:
            options.expire_due(s, clock.today())

    server.tasks.register("options", expire_options, Every(3600), last.get("options"))

    def bitcoin(ctx: TaskContext) -> None:
        """Self-custody wallets read from the explorer or node (S1.6.2)."""
        from .bitcoin import sync

        sync.sync_all(server, ctx)

    server.tasks.register("bitcoin", bitcoin, Every(3600), last.get("bitcoin"))

    def links(ctx: TaskContext) -> None:
        """An exchange with each linked server (S11.4): hourly. Dev mode with stubs makes no
        outside calls, so its seeded link is left as it is."""
        from .links import manage

        if server.config.stubs:
            return

        manage.exchange_all(server, ctx)

    server.tasks.register("links", links, Every(3600), last.get("links"))

    def lock_copies(ctx: TaskContext) -> None:
        """Lock each linked copy that has gone unused past its time (S11.9.4.2)."""
        from .links import copies as linked

        linked.sweep(server)

    server.tasks.register("linked-copies", lock_copies, Every(60), last.get("linked-copies"))

    from . import alerts

    server.tasks.register(
        "alerts", lambda ctx: alerts.evaluate(server), Every(900), last.get("alerts")
    )
    server.tasks.register(
        "alert-summaries",
        lambda ctx: alerts.daily_summaries(server),
        Every(600),
        last.get("alert-summaries"),
    )
    server.services.mailer.notify = lambda: server.tasks.run_now("mail")


class AlreadyUnlocked(Exception):
    pass


def build(server: Server, master_key: bytes) -> None:
    """Open the store with the phrase's key and make the server whole (S15.4.3). The master
    key is used here and not kept."""
    config = server.config
    store = maintenance.open_store(config, master_key)
    pricing.install()
    server.store = store
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
    take_host_events(server)
    load_copy_folders(server)


def load_copy_folders(server: Server) -> None:
    """Each link's copy folder, by its random name (S11.9.1), for the copies' paths."""
    from sqlalchemy import select

    from .links import copy as linked
    from .store.entities.links import Link

    with server.db.read() as s:
        for link_id, name in s.execute(
            select(Link.id, Link.copyFolder).where(Link.copyFolder.is_not(None))
        ):
            linked.NAMES[link_id] = name


def take_host_events(server: Server) -> int:
    """What the host's one-off commands queued (keys verify, rotate), into Activity."""
    from . import activity

    events = maintenance.take_host_events(server.config)
    if not events:
        return 0
    with server.db.tx() as s:
        for e in events:
            activity.record(
                s,
                str(e.get("kind", "host")),
                actor=None,
                via="host",
                for_admins=True,
                detail={**(e.get("detail") or {}), "at": e.get("at")},
            )
    return len(events)


async def unlock(server: Server, master_key: bytes, seed: bool = False) -> None:
    """The phrase given (from the unlock page, `keys unlock`, or dev mode): the server opens
    its store and starts its tasks. Once per start; a restart locks it again (S15.4.3)."""
    if server.unlocking is None:
        server.unlocking = asyncio.Lock()
    async with server.unlocking:
        if server.store is not None:
            raise AlreadyUnlocked
        await asyncio.to_thread(build, server, master_key)
        if server.config.dev:
            from .dev import devmode

            await asyncio.to_thread(devmode.after_start, server, seed)
        from .receipts.reading import Reader

        server.reader = Reader(server)
        server.tasks.start()
        server.reader.start()
        server.ready = True
        log.info("unlocked: %s", server.store.keys.master_id and server.version)


async def start(config: Config, seed: bool = False) -> int:
    dev_key: bytes | None = None
    if config.dev:
        from .dev import devmode

        dev_key = devmode.prepare(config)
    from .store.maintenance import lock_data_dir

    lock = lock_data_dir(config, "only one server may use a data directory")  # noqa: F841 - held while running
    if not config.keyring_path.exists():
        raise RefuseStart(
            f"the keyring {config.keyring_path} is missing: run `moneykata keys init` on a new "
            "server, or `db restore` a backup"
        )
    server = Server(config=config)
    server.unlocking = asyncio.Lock()
    app = create_app(server)
    server.events.bind(asyncio.get_running_loop())
    if dev_key is not None:
        await unlock(server, dev_key, seed=seed)

    async def on_stop() -> None:
        server.ready = False
        await server.events.close_all()
        if server.store is not None:
            server.tasks.stop()
            server.reader.stop()

    scheme = "https" if config.mode == "tls" else "http"
    log.info(
        "MoneyKata %s%s listening on %s://%s:%s%s",
        server.version,
        " (dev)" if config.dev else "",
        scheme,
        config.host,
        config.port,
        "" if server.store is not None else ": locked until the recovery phrase is entered",
    )
    try:
        await listener.run(app, config, on_stop)
    finally:
        if server.store is not None:
            server.db.dispose()
    log.info("stopped")
    return 0
