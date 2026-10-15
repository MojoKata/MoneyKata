"""Signing in and out, the default admin's setup, invitations, password reset and the live
stream (requirements S10.1, S12.6, S13.7)."""

import asyncio
import time

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

from .. import activity, settings, timezones
from ..auth import passwords, sessions, signup, twostep
from ..auth import users as accounts
from ..errors import Problem, refuse
from ..ratelimit import Window, too_many
from ..store.entities.users import User
from .conventions import ExactRoute, Loose, Model
from .deps import Caller, caller_in_setup, caller_quiet, server, set_cookie
from .stream import stream

router = APIRouter(prefix="/ui/api", route_class=ExactRoute, tags=["session"])
_by_address = Window(30, 15 * 60)


class Household(Model):
    name: str
    avatar: Loose


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
    bitcoinUnit: str  # btc or sats (S1.6.4)


class SessionInfo(Model):
    user: Me
    household: Household
    version: str
    dev: bool
    serverName: str


class SignIn(Model):
    login: str
    password: str


class TwoStepNeeded(Model):
    """The password was right and two-step sign-in is on: the code comes next (S10.1.6)."""

    twoStepToken: str


class TwoStepCode(Model):
    token: str
    code: str


class Setup(Model):
    password: str
    email: str
    displayName: str | None = None
    sex: str | None = None  # the default admin's person (S10.10.1)


class Password(Model):
    password: str


class Login(Model):
    login: str


class TokenPassword(Model):
    token: str
    password: str


class Token(Model):
    token: str


class SignupOpen(Model):
    """Whether the sign-in screen offers Sign up, and to which email domains."""

    open: bool
    domains: list[str]


class SignupForm(Model):
    displayName: str
    username: str
    email: str
    password: str
    sex: str | None = None


class SignupConfirmed(Model):
    displayName: str
    household: str


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
            bitcoinUnit=user.bitcoinUnit,
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


@router.post(
    "/session",
    response_model=SessionInfo,
    responses={202: {"model": TwoStepNeeded}, 401: {}, 403: {}, 429: {}},
)
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
    two_step = None
    with srv.db.tx() as s:
        user = accounts.by_login(s, login)
        ok = passwords.verify(user.passwordHash if user else None, body.password)
        if not ok:
            _failed(s, guard, login, address, user)
            failed = True
        else:
            failed = False
            if not user.active:
                raise Problem(403, "account-disabled", "This account is disabled.")
            if passwords.needs_rehash(user.passwordHash):
                user.passwordHash = passwords.hash_password(body.password)
            if twostep.is_on(user):
                # No session until the code: failed codes count toward the same lockout.
                two_step = twostep.start_sign_in(s, user)
            else:
                guard.succeeded(login)
                admin, token = _signed_in(s, user)
    if failed:
        # Committed above: failures and lockouts stay in Activity.
        raise Problem(401, "bad-credentials", "The username or password is not right.")
    if two_step:
        return JSONResponse(TwoStepNeeded(twoStepToken=two_step).model_dump(), status_code=202)
    set_cookie(request, token)
    return info(request, user, admin)


@router.post("/session/two-step", response_model=SessionInfo, responses={401: {}, 429: {}})
def sign_in_code(body: TwoStepCode, request: Request):
    """The second step: a code from the app, or one of the recovery codes (S10.1.6)."""
    srv = server(request)
    guard = srv.sign_in
    address = _address(request)
    with srv.db.tx() as s:
        user = twostep.pending_user(s, body.token)
        login = user.username
        locked = guard.locked(login)
        if locked:
            raise too_many(locked, "failed sign-ins for this user")
        if not user.active or user.deleted:
            raise Problem(403, "account-disabled", "This account is disabled.")
        how = twostep.check_code(s, srv.keys.secrets, user, body.code)
        if how is None:
            _failed(s, guard, login, address, user)
        else:
            guard.succeeded(login)
            twostep.finish_sign_in(s, body.token)
            admin, token = _signed_in(
                s, user, "signin" if how == "code" else "signin.recovery-code"
            )
    if how is None:
        delay = guard.address_delay(address)
        if delay:
            time.sleep(delay)
        raise refuse("code", "code-wrong", "That code isn't right.", 401)
    set_cookie(request, token)
    return info(request, user, admin)


def _failed(s, guard, login: str, address: str, user: User | None) -> None:
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


def _signed_in(s, user: User, kind: str = "signin") -> tuple[bool, str]:
    admin = accounts.is_admin(s, user.id)
    token = sessions.create(s, user.id, admin, user.needsSetup)
    user.lastSignInAt = sessions.now()
    activity.record(
        s,
        kind,
        actor=user.id,
        subject_kind="user",
        subject_id=user.id,
        owner=user.id,
        for_admins=kind != "signin",
    )
    return admin, token


@router.delete("/session", status_code=204)
def sign_out(request: Request, c: Caller = Depends(caller_in_setup)):
    """Signing out ends every session of the user at once (S13.7.1)."""
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
        accounts.finish_setup(s, user, body.password, body.email, body.displayName, body.sex)
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
    """The answer is the same whether or not the user exists (S10.1.5)."""
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


@router.get("/signup", response_model=SignupOpen)
def signup_open(request: Request):
    srv = server(request)
    with srv.db.read() as s:
        on, domains = signup.open_to(s, srv.config.dev)
    return SignupOpen(open=on, domains=domains)


@router.post("/signup", status_code=202, responses={403: {}, 422: {}, 429: {}})
def signup_request(body: SignupForm, request: Request):
    """The answer is the same whether or not the email already has an account (S10.1.4)."""
    srv = server(request)
    _throttle(request)
    with srv.db.tx() as s:
        signup.request(
            s,
            srv.services,
            body.displayName,
            body.username,
            body.email,
            body.password,
            body.sex,
        )
    return Response(status_code=202)


@router.post("/signup/confirm", response_model=SignupConfirmed)
def signup_confirm(body: Token, request: Request):
    srv = server(request)
    _throttle(request)
    with srv.db.tx() as s:
        req = signup.confirm(s, body.token)
        out = SignupConfirmed(
            displayName=req.displayName, household=settings.get(s, "householdName")
        )
        admins = accounts.admin_ids(s)
    srv.events.publish("signup", {}, users=admins)
    return out


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
    """The live stream (S12.6): what changed, never data. It ends after a few minutes and
    the browser reconnects; it never extends the session."""
    srv = server(request)
    token_hash = c.session.tokenHash
    sub = srv.events.subscribe(c.id, token_hash)

    token = request.cookies.get(sessions.COOKIE)

    def check() -> str | None:
        with srv.db.read() as s:
            found = sessions.find(s, token)
            if found is None:
                return "signed-out"
            if found.ended:
                return "expired"
            user = s.get(User, c.id)
            return None if user and user.active else "disabled"

    async def ended() -> str | None:
        # On a worker thread: a database call on the event loop would hold up every request.
        return await asyncio.to_thread(check)

    hello = {"version": srv.version, "badges": srv.badges(c)}
    return StreamingResponse(
        stream(srv.events, sub, hello, ended, seconds=srv.stream_seconds),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )
