"""Signing in and out, the default admin's setup, invitations, password reset and the live
stream (requirements §13.1, §15.6, §16.7)."""

import time

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response, StreamingResponse

from .. import activity, settings, timezones
from ..auth import passwords, sessions
from ..auth import users as accounts
from ..errors import Problem
from ..ratelimit import Window, too_many
from ..store.entities.users import User
from .conventions import Model
from .deps import Caller, caller_in_setup, caller_quiet, server, set_cookie
from .stream import stream

router = APIRouter(prefix="/ui/api", tags=["session"])
_by_address = Window(30, 15 * 60)


class Household(Model):
    name: str
    avatar: dict


class Me(Model):
    id: str
    username: str
    displayName: str
    email: str | None
    avatar: str | None
    admin: bool
    needsSetup: bool
    timeZone: str
    zone: str
    theme: str


class SessionInfo(Model):
    user: Me
    household: Household
    version: str
    dev: bool
    serverName: str


class SignIn(Model):
    login: str
    password: str


class Setup(Model):
    password: str
    email: str
    displayName: str | None = None


class Password(Model):
    password: str


class Login(Model):
    login: str


class TokenPassword(Model):
    token: str
    password: str


class Token(Model):
    token: str


class InvitationInfo(Model):
    username: str
    displayName: str
    household: str


def info(request: Request, user: User, admin: bool) -> SessionInfo:
    srv = server(request)
    with srv.db.read() as s:
        house = Household(
            name=settings.get(s, "householdName"), avatar=settings.get(s, "householdAvatar")
        )
        name = settings.get(s, "serverName")
    return SessionInfo(
        user=Me(
            id=user.id,
            username=user.username,
            displayName=user.displayName,
            email=user.email,
            avatar=user.avatar,
            admin=admin,
            needsSetup=user.needsSetup,
            timeZone=user.timeZone,
            zone=timezones.zone_for(user.timeZone),
            theme=user.theme,
        ),
        household=house,
        version=srv.version,
        dev=srv.config.dev,
        serverName=name,
    )


def _address(request: Request) -> str:
    return request.client.host if request.client else "-"


def _throttle(request: Request) -> None:
    wait = _by_address.hit(_address(request))
    if wait:
        raise too_many(wait, "attempts")


@router.get("/session", response_model=SessionInfo)
def get_session(request: Request, c: Caller = Depends(caller_in_setup)):
    return info(request, c.user, c.admin)


@router.post("/session", response_model=SessionInfo, responses={401: {}, 403: {}, 429: {}})
def sign_in(body: SignIn, request: Request):
    srv = server(request)
    guard = srv.sign_in
    login = body.login.strip().lower()
    address = _address(request)
    locked = guard.locked(login)
    if locked:
        raise too_many(locked, "failed sign-ins for this user")
    delay = guard.address_delay(address)
    if delay:
        time.sleep(delay)
    with srv.db.tx() as s:
        user = accounts.by_login(s, login)
        ok = passwords.verify(user.passwordHash if user else None, body.password)
        if not ok:
            failures = settings.get(s, "lockoutFailures")
            minutes = settings.get(s, "lockoutMinutes")
            now_locked = guard.failed(login, address, failures, minutes)
            activity.record(
                s,
                "signin.locked" if now_locked else "signin.failed",
                actor=None,
                subject_kind="user" if user else None,
                subject_id=user.id if user else None,
                owner=user.id if user else None,
                for_admins=True,
            )
            failed = True
        else:
            failed = False
            if not user.active:
                raise Problem(403, "account-disabled", "This account is disabled.")
            guard.succeeded(login)
            if passwords.needs_rehash(user.passwordHash):
                user.passwordHash = passwords.hash_password(body.password)
            admin = accounts.is_admin(s, user.id)
            token = sessions.create(s, user.id, admin, user.needsSetup)
            user.lastSignInAt = sessions.now()
            activity.record(
                s, "signin", actor=user.id, subject_kind="user", subject_id=user.id, owner=user.id
            )
    if failed:
        # Committed above: failures and lockouts stay in Activity.
        raise Problem(401, "bad-credentials", "The username or password is not right.")
    set_cookie(request, token)
    return info(request, user, admin)


@router.delete("/session", status_code=204)
def sign_out(request: Request, c: Caller = Depends(caller_in_setup)):
    """Signing out ends every session of the user at once (§16.7.1)."""
    srv = server(request)
    with srv.db.tx() as s:
        sessions.end_all(s, c.id)
        activity.record(s, "signout", actor=c.id, subject_kind="user", subject_id=c.id, owner=c.id)
    srv.events.end_user(c.id, "signed-out")
    set_cookie(request, None)
    return Response(status_code=204)


@router.post("/session/setup", response_model=SessionInfo)
def setup(body: Setup, request: Request, c: Caller = Depends(caller_in_setup)):
    if not c.user.needsSetup:
        raise Problem(409, "setup-done", "This account is already set up.")
    srv = server(request)
    with srv.db.tx() as s:
        user = s.get(User, c.id)
        accounts.finish_setup(s, user, body.password, body.email, body.displayName)
        sessions.end_all(s, user.id)
        admin = accounts.is_admin(s, user.id)
        token = sessions.create(s, user.id, admin, False)
    set_cookie(request, token)
    return info(request, user, admin)


@router.post("/session/reauth", status_code=204)
def reauth(body: Password, request: Request, c: Caller = Depends(caller_in_setup)):
    srv = server(request)
    _throttle(request)
    with srv.db.tx() as s:
        user = s.get(User, c.id)
        if not passwords.verify(user.passwordHash, body.password):
            raise Problem(401, "password-wrong", "That is not your password.")
        row = sessions.find(s, request.cookies.get(sessions.COOKIE)).session
        row.authAt = sessions.now()
    return Response(status_code=204)


@router.post("/password-reset", status_code=202)
def password_reset(body: Login, request: Request):
    """The answer is the same whether or not the user exists (§13.1.5)."""
    srv = server(request)
    _throttle(request)
    with srv.db.tx() as s:
        accounts.request_reset(s, srv.services, body.login)
    return Response(status_code=202)


@router.post("/password-reset/confirm", status_code=204)
def password_reset_confirm(body: TokenPassword, request: Request):
    srv = server(request)
    _throttle(request)
    with srv.db.tx() as s:
        user = accounts.reset_password(s, srv.services, body.token, body.password)
    srv.events.end_user(user.id, "signed-out")
    return Response(status_code=204)


@router.post("/invitations/lookup", response_model=InvitationInfo)
def invitation_lookup(body: Token, request: Request):
    srv = server(request)
    _throttle(request)
    with srv.db.read() as s:
        user = accounts.peek_invitation(s, body.token)
        return InvitationInfo(
            username=user.username,
            displayName=user.displayName,
            household=settings.get(s, "householdName"),
        )


@router.post("/invitations/accept", response_model=SessionInfo)
def invitation_accept(body: TokenPassword, request: Request):
    srv = server(request)
    _throttle(request)
    with srv.db.tx() as s:
        user = accounts.accept_invitation(s, body.token, body.password)
        admin = accounts.is_admin(s, user.id)
        token = sessions.create(s, user.id, admin, False)
        user.lastSignInAt = sessions.now()
    set_cookie(request, token)
    return info(request, user, admin)


@router.post("/email-change/confirm", status_code=204)
def email_change_confirm(body: Token, request: Request):
    srv = server(request)
    _throttle(request)
    with srv.db.tx() as s:
        accounts.confirm_email_change(s, body.token)
    return Response(status_code=204)


@router.post("/reactivation-requests", status_code=202)
def reactivation_request(body: SignIn, request: Request):
    srv = server(request)
    _throttle(request)
    with srv.db.tx() as s:
        accounts.ask_reactivation(s, body.login, body.password)
    return Response(status_code=202)


@router.get(
    "/events",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}}},
)
def events(request: Request, c: Caller = Depends(caller_quiet)):
    """The live stream (§15.6): what changed, never data. It ends after a few minutes and
    the browser reconnects; it never extends the session."""
    srv = server(request)
    token_hash = c.session.tokenHash
    sub = srv.events.subscribe(c.id, token_hash)

    async def ended() -> str | None:
        with srv.db.read() as s:
            found = sessions.find(s, request.cookies.get(sessions.COOKIE))
            if found is None:
                return "signed-out"
            if found.ended:
                return "expired"
            user = s.get(User, c.id)
            return None if user and user.active else "disabled"

    hello = {"version": srv.version, "badges": srv.badges(c)}
    return StreamingResponse(
        stream(srv.events, sub, hello, ended, seconds=srv.stream_seconds),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )
