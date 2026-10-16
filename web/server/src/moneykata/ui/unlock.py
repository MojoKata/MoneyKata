"""Unlocking the server (requirements S13.6, S15.4.3): it starts locked, with no key anywhere,
until an admin enters the recovery phrase here (the unlock page) or with `moneykata keys
unlock` on the host, which posts to this same route. The phrase is the authentication: no
user can be checked before the database opens. Wrong phrases count toward the sign-in
lockout, and every attempt is logged.

Rotation through the running server (S15.7.1) lives here too: `moneykata keys rotate`, run
inside the container, posts the new phrase over loopback, and the server re-wraps the data
key it holds. Only loopback reaches it: host access is the authentication, as for every
other key command."""

import asyncio
import ipaddress
import logging

from fastapi import APIRouter, Request

from ..config import RefuseStart
from ..errors import Problem
from ..keys import cli as keys_cli
from ..keys import master, phrase
from .conventions import ExactRoute, Model
from .deps import server

log = logging.getLogger("moneykata.unlock")
router = APIRouter(prefix="/ui/api", route_class=ExactRoute, tags=["unlock"])
LOGIN = "recovery phrase"  # the lockout's name for unlock attempts


class Phrase(Model):
    phrase: str


class LockState(Model):
    locked: bool
    fingerprint: str | None  # of the key the keyring is wrapped under
    version: str


def _state(srv) -> LockState:
    try:
        fp = keys_cli.fingerprint_of(srv.config)
    except RefuseStart:
        fp = None
    return LockState(locked=srv.store is None, fingerprint=fp, version=srv.version)


@router.get("/unlock", response_model=LockState)
def lock_state(request: Request):
    return _state(server(request))


@router.post("/unlock", response_model=LockState)
async def unlock(body: Phrase, request: Request):
    from .. import runtime

    srv = server(request)
    if srv.store is not None:
        raise Problem(409, "unlocked-already", "MoneyKata is already unlocked.")
    address = request.client.host if request.client else "-"
    guard = srv.sign_in
    wait = guard.locked(LOGIN)
    if wait:
        raise Problem(
            429,
            "locked-out",
            "Too many wrong phrases: try again later.",
            headers={"Retry-After": str(int(wait) + 1)},
        )
    delay = guard.address_delay(address)
    if delay:
        await asyncio.sleep(delay)
    try:
        key = phrase.from_words(body.phrase)
    except phrase.PhraseError as e:
        guard.failed(LOGIN, address)
        log.warning("unlock refused from %s: not a phrase", address)
        raise Problem(422, "phrase-invalid", f"Not a recovery phrase: {e}") from None
    try:
        await runtime.unlock(srv, key)
    except master.WrongPhrase:
        guard.failed(LOGIN, address)
        log.warning("unlock refused from %s: wrong phrase (%s)", address, master.fingerprint(key))
        raise Problem(403, "phrase-wrong", "Those words are not this server's key.") from None
    except runtime.AlreadyUnlocked:
        raise Problem(409, "unlocked-already", "MoneyKata is already unlocked.") from None
    except RefuseStart as e:
        log.error("refusing to unlock: %s", e)
        raise Problem(
            503, "cannot-unlock", "The server cannot open its data: see its log."
        ) from None
    log.info("unlocked from %s", address)
    return _state(srv)


def _loopback(request: Request) -> bool:
    try:
        return ipaddress.ip_address(request.client.host if request.client else "").is_loopback
    except ValueError:
        return False


@router.post("/keys/rotate", response_model=dict)
def rotate(body: Phrase, request: Request):
    """`moneykata keys rotate` against the running server: the new phrase's key wraps the data
    key the server holds; the keyring is written with the old key recorded. From loopback
    only (S15.4.4)."""
    from .. import activity
    from ..store import maintenance

    srv = server(request)
    if not _loopback(request):
        raise Problem(404, "not-found", "Not found.")
    if srv.store is None:
        raise Problem(503, "locked", "Unlock the server first, or rotate it offline.")
    try:
        new_key = phrase.from_words(body.phrase)
    except phrase.PhraseError as e:
        raise Problem(422, "phrase-invalid", f"Not a recovery phrase: {e}") from None
    old_fp = master.fingerprint(srv.store.keys.master_id)
    try:
        srv.store = maintenance.rotate_running(srv.config, srv.store, new_key)
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
            detail={"from": old_fp, "to": new_fp},
        )
    log.info("the master key was rotated through the running server: %s -> %s", old_fp, new_fp)
    return {"from": old_fp, "to": new_fp}
