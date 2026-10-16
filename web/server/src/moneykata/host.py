"""Host commands' way in (requirements S13.6, S15.4.2, S15.4.7): a Unix socket,
`/run/moneykata/sock`, in a 0700 directory of the server's account, where `keys unlock`,
`keys rotate` and `db backup`, run inside the server's container, reach the running server.
It is no network listener: only the server's own account (or root) inside the container can
open it, so reaching it is the host access that authenticates these commands. Nothing that
reaches the listener, a forged `X-Forwarded-For` included, reaches these routes."""

import logging
import os
import stat
from contextlib import contextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI, Request
from hypercorn.config import Config as HypercornConfig
from pydantic import Field

from . import errors
from .config import Config, RefuseStart
from .errors import Problem
from .keys import master, phrase
from .ui.conventions import ExactRoute, Model
from .ui.deps import server

log = logging.getLogger("moneykata.host")
router = APIRouter(prefix="/host", route_class=ExactRoute)
# The address the sign-in lockout and the log give a host command.
CALLER = "host"


class Phrase(Model):
    phrase: str


class RotateIn(Model):
    phrase: str  # the new phrase
    oldPhrase: str | None = None  # the current one when known: opens copies under earlier data keys
    copies: dict[str, str] = Field(default_factory=dict)  # name: rewrap, delete or leave


@router.get("/unlock")
def lock_state(request: Request):
    from .ui.unlock import state

    return state(server(request)).model_dump(mode="json")


@router.post("/unlock")
async def unlock(body: Phrase, request: Request):
    """`moneykata keys unlock` (S15.4.2): the same unlock as the locked screen's."""
    from .ui.unlock import try_unlock

    return (await try_unlock(server(request), body.phrase, CALLER)).model_dump(mode="json")


@router.get("/keys/copies")
def copies_for_rotation(request: Request):
    """The copies on this host, for `keys rotate` to ask about (S15.7.1)."""
    from .ui.settings import copies_out

    srv = server(request)
    if srv.store is None:
        raise Problem(503, "locked", "Unlock the server first.")
    return copies_out(srv).model_dump(mode="json")


@router.post("/keys/rotate")
def rotate(body: RotateIn, request: Request):
    """`moneykata keys rotate` against the running server: the new phrase's key wraps the data
    key the server holds; the keyring is written with the old key recorded; each copy on the
    host is re-wrapped, deleted or left as chosen."""
    from . import activity
    from .store import maintenance

    srv = server(request)
    if srv.store is None:
        raise Problem(503, "locked", "Unlock the server first, or rotate it offline.")
    try:
        new_key = phrase.from_words(body.phrase)
        old_key = phrase.from_words(body.oldPhrase) if body.oldPhrase else None
    except phrase.PhraseError as e:
        raise Problem(422, "phrase-invalid", f"Not a recovery phrase: {e}") from None
    if any(v not in ("rewrap", "delete", "leave") for v in body.copies.values()):
        raise Problem(422, "choice-invalid", "Each copy: rewrap, delete or leave.")
    with srv.maintenance_lock:
        if srv.tasks.status().get("reencrypt", {}).get("running"):
            raise Problem(409, "reencrypt-running", "A re-encryption is running: wait for it.")
        old_fp = master.fingerprint(srv.store.keys.master_id)
        try:
            srv.store, outcomes = maintenance.rotate_running(
                srv.config, srv.store, new_key, body.copies, old_key
            )
        except RefuseStart as e:
            raise Problem(409, "reencrypt-pending", str(e)) from None
    new_fp = master.fingerprint(new_key)
    with srv.db.tx() as s:
        activity.record(
            s,
            "key.rotated",
            actor=None,
            via="host",
            for_admins=True,
            detail={"from": old_fp, "to": new_fp, "copies": outcomes},
        )
    log.info("the master key was rotated through the running server: %s -> %s", old_fp, new_fp)
    return {"from": old_fp, "to": new_fp, "copies": outcomes}


@router.post("/backup")
def backup(request: Request):
    """`moneykata db backup` against the running server (S14.6): a verified backup now, and
    the oldest beyond the number kept pruned, as the daily task does."""
    from . import activity, settings
    from .store import maintenance

    srv = server(request)
    if srv.store is None:
        raise Problem(503, "locked", "Unlock the server first.")
    with srv.maintenance_lock:
        path = maintenance.backup(srv.config, srv.store)
        with srv.db.read() as s:
            keep = settings.get(s, "backupCopies")
        maintenance.prune(srv.config, keep)
    with srv.db.tx() as s:
        activity.record(
            s, "db.backup", actor=None, via="host", for_admins=True, detail={"name": path.name}
        )
    return {"name": path.name, "path": str(path)}


def create_host_app(srv) -> FastAPI:
    app = FastAPI(title="MoneyKata host", openapi_url=None, docs_url=None, redoc_url=None)
    app.state.server = srv
    errors.install(app)
    app.include_router(router)
    return app


def prepare(config: Config) -> Path:
    """The socket's directory: made 0700 when missing, and refused when another account owns it
    or others may open it, since whoever opens the socket is trusted as the host."""
    folder = config.socket_path.parent
    try:
        folder.mkdir(mode=0o700, parents=True, exist_ok=True)
        st = folder.stat()
    except OSError as e:
        raise RefuseStart(
            f"the host commands' socket can't be made in {folder}: {e.strerror} (the container "
            f"needs a tmpfs there owned by its account, as compose.yaml gives it)"
        ) from None
    if st.st_uid != os.geteuid():
        raise RefuseStart(f"{folder} belongs to another account: it must be this server's own")
    if stat.S_IMODE(st.st_mode) & 0o077:
        os.chmod(folder, 0o700)
    return config.socket_path


def hypercorn_config(config: Config) -> HypercornConfig:
    hc = HypercornConfig()
    hc.bind = [f"unix:{prepare(config)}"]
    hc.umask = 0o177  # the socket itself 0600
    hc.graceful_timeout = 5
    hc.accesslog = None
    hc.errorlog = logging.getLogger("hypercorn.error")
    hc.include_server_header = False
    return hc


class NotRunning(Exception):
    """No server answers on this host's socket."""


@contextmanager
def client(config: Config, timeout: float = 30):
    """The command line's side: HTTP over the socket, never the network."""
    import httpx

    if not config.socket_path.exists():
        raise NotRunning(f"no server is running here (no socket at {config.socket_path})")
    transport = httpx.HTTPTransport(uds=str(config.socket_path))
    with httpx.Client(transport=transport, base_url="http://host", timeout=timeout) as c:
        try:
            yield c
        except httpx.TransportError as e:
            raise NotRunning(f"the server isn't answering on {config.socket_path}: {e}") from None


def detail(r) -> str:
    try:
        return r.json().get("detail") or r.text
    except ValueError:
        return r.text
