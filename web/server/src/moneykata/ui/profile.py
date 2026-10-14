"""Profile (requirements S12.2.16): name, email, avatar, password, two-step sign-in, time
zone, theme, birth year, spouse for wash sales and alert emails. Assumptions and access tokens
come with their features."""

import datetime as dt
import re

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from sqlalchemy import false, select

from .. import activity, settings, timezones
from ..auth import sessions, twostep
from ..auth import users as accounts
from ..errors import refuse
from ..store.entities.users import OneTimeToken, User
from .conventions import Model, if_match, stale
from .deps import Caller, caller, recent_auth, server, set_cookie

router = APIRouter(prefix="/ui/api", tags=["profile"])
AVATAR = re.compile(r"^data:image/(png|jpeg|webp);base64,[A-Za-z0-9+/=]+$")
AVATAR_MAX = 256 * 1024


class Person(Model):
    id: str
    displayName: str


class TwoStep(Model):
    on: bool
    since: dt.datetime | None
    recoveryCodesLeft: int


class TwoStepSetup(Model):
    """What an authenticator app needs: the QR code, or the key typed by hand."""

    secret: str
    uri: str
    qrImage: str


class TwoStepConfirm(Model):
    code: str


class RecoveryCodes(Model):
    """Shown once: only their hashes are kept."""

    codes: list[str]


class Profile(Model):
    id: str
    username: str
    displayName: str
    email: str | None
    pendingEmail: str | None
    avatar: str | None
    timeZone: str
    zone: str
    theme: str
    birthYear: int | None
    spouseId: str | None
    alertEmails: str
    twoStep: TwoStep
    people: list[Person]
    version: int


class ProfileChange(Model):
    displayName: str | None = None
    avatar: str | None = None
    timeZone: str | None = None
    theme: str | None = None
    birthYear: int | None = None
    spouseId: str | None = None
    alertEmails: str | None = None


class PasswordChange(Model):
    currentPassword: str
    newPassword: str


class EmailChange(Model):
    email: str


class Zones(Model):
    server: str
    zones: list[str]


def profile(s, u: User) -> Profile:
    pending = s.scalars(
        select(OneTimeToken.data).where(
            OneTimeToken.userId == u.id,
            OneTimeToken.purpose == "email-change",
            OneTimeToken.expiresAt > sessions.now(),
        )
    ).first()
    others = s.scalars(
        select(User)
        .where(User.deleted == false(), User.active, User.id != u.id, User.linkId.is_(None))
        .order_by(User.displayName)
    ).all()
    return Profile(
        id=u.id,
        username=u.username,
        displayName=u.displayName,
        email=u.email,
        pendingEmail=pending,
        avatar=u.avatar,
        timeZone=u.timeZone,
        zone=timezones.zone_for(u.timeZone),
        theme=u.theme,
        birthYear=u.birthYear,
        spouseId=u.spouseId,
        alertEmails=u.alertEmails,
        twoStep=TwoStep(
            on=twostep.is_on(u),
            since=u.twoStepAt,
            recoveryCodesLeft=twostep.codes_left(s, u.id),
        ),
        people=[Person(id=o.id, displayName=o.displayName) for o in others],
        version=u.version,
    )


@router.get("/profile", response_model=Profile)
def get_profile(request: Request, c: Caller = Depends(caller)):
    with server(request).db.read() as s:
        return profile(s, s.get(User, c.id))


@router.patch("/profile", response_model=Profile)
def change_profile(
    body: ProfileChange,
    request: Request,
    c: Caller = Depends(caller),
    version: int = Depends(if_match),
):
    sent = body.model_fields_set
    with server(request).db.tx() as s:
        u = s.get(User, c.id)
        if u.version != version:
            raise stale(profile(s, u))
        fields = []
        if "displayName" in sent:
            name = (body.displayName or "").strip()
            if not name or len(name) > 80:
                raise refuse("displayName", "name-invalid", "Enter a name of up to 80 characters.")
            u.displayName = name
            fields.append("displayName")
        if "avatar" in sent:
            if body.avatar is not None and (
                not AVATAR.match(body.avatar) or len(body.avatar) > AVATAR_MAX
            ):
                raise refuse(
                    "avatar", "avatar-invalid", "Use a PNG, JPEG or WebP image under 192 KB."
                )
            u.avatar = body.avatar
            fields.append("avatar")
        if "timeZone" in sent:
            tz = body.timeZone or "auto"
            if tz != "auto" and not timezones.valid(tz):
                raise refuse("timeZone", "zone-invalid", "Choose a time zone from the list.")
            u.timeZone = tz
            fields.append("timeZone")
        if "theme" in sent:
            if body.theme not in ("dark", "light", "system"):
                raise refuse("theme", "theme-invalid", "Dark, light or the system's.")
            u.theme = body.theme
            fields.append("theme")
        if "birthYear" in sent:
            if body.birthYear is not None and not 1900 <= body.birthYear <= 2100:
                raise refuse("birthYear", "year-invalid", "Enter a year such as 1979.")
            u.birthYear = body.birthYear
            fields.append("birthYear")
        if "spouseId" in sent:
            if body.spouseId is not None:
                other = s.get(User, body.spouseId)
                if other is None or other.deleted or other.id == u.id or other.linkId:
                    raise refuse("spouseId", "user-unknown", "Choose a user of this server.")
            u.spouseId = body.spouseId
            fields.append("spouseId")
        if "alertEmails" in sent:
            if body.alertEmails not in ("each", "daily", "none"):
                raise refuse(
                    "alertEmails", "choice-invalid", "Each alert, a daily summary or none."
                )
            u.alertEmails = body.alertEmails
            fields.append("alertEmails")
        if fields:
            activity.record(
                s,
                "profile.updated",
                actor=u.id,
                subject_kind="user",
                subject_id=u.id,
                owner=u.id,
                detail={"fields": fields},
            )
        s.flush()
        return profile(s, u)


@router.post("/profile/password", status_code=204)
def change_password(body: PasswordChange, request: Request, c: Caller = Depends(caller)):
    """Ends every session; this browser gets a fresh one (S13.7.1)."""
    srv = server(request)
    with srv.db.tx() as s:
        u = s.get(User, c.id)
        accounts.change_password(s, srv.services, u, body.currentPassword, body.newPassword)
        token = sessions.create(s, u.id, c.admin, False)
    srv.events.end_user(c.id, "signed-out")
    set_cookie(request, token)
    return Response(status_code=204)


@router.post("/profile/email", status_code=202)
def change_email(body: EmailChange, request: Request, c: Caller = Depends(caller)):
    recent_auth(c)
    srv = server(request)
    with srv.db.tx() as s:
        accounts.request_email_change(s, srv.services, s.get(User, c.id), body.email)
    return Response(status_code=202)


@router.post("/profile/two-step", response_model=TwoStepSetup)
def two_step_begin(request: Request, c: Caller = Depends(caller)):
    """Turning two-step on starts here; it is on once a code from the app is confirmed."""
    recent_auth(c)
    srv = server(request)
    with srv.db.tx() as s:
        u = s.get(User, c.id)
        seed = twostep.begin(s, srv.keys.secrets, u)
        link = twostep.uri(seed, u.username, settings.get(s, "serverName") or "MoneyKata")
    return TwoStepSetup(secret=seed, uri=link, qrImage=twostep.qr_image(link))


@router.post("/profile/two-step/confirm", response_model=RecoveryCodes)
def two_step_confirm(body: TwoStepConfirm, request: Request, c: Caller = Depends(caller)):
    srv = server(request)
    with srv.db.tx() as s:
        codes = twostep.confirm(s, srv.services, srv.keys.secrets, s.get(User, c.id), body.code)
    return RecoveryCodes(codes=codes)


@router.post("/profile/two-step/recovery-codes", response_model=RecoveryCodes)
def two_step_codes(request: Request, c: Caller = Depends(caller)):
    """New codes replace every old one."""
    recent_auth(c)
    srv = server(request)
    with srv.db.tx() as s:
        return RecoveryCodes(codes=twostep.new_recovery_codes(s, s.get(User, c.id)))


@router.delete("/profile/two-step", status_code=204)
def two_step_off(request: Request, c: Caller = Depends(caller)):
    recent_auth(c)
    srv = server(request)
    with srv.db.tx() as s:
        u = s.get(User, c.id)
        twostep.turn_off(s, srv.services, u, u)
    return Response(status_code=204)


@router.get("/timezones", response_model=Zones)
def zones(request: Request, c: Caller = Depends(caller)):
    return Zones(server=timezones.host_zone(), zones=timezones.names())
