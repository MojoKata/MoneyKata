"""Users and Groups, for admins (requirements S10.1)."""

import datetime as dt

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response
from pydantic import Field
from sqlalchemy import false, select

from ..auth import users as accounts
from ..errors import Problem
from ..store.entities.users import Group, User
from .conventions import Model, if_match, stale
from .deps import Caller, admin, server

router = APIRouter(prefix="/ui/api", tags=["users"])


class UserRow(Model):
    id: str
    username: str
    displayName: str
    email: str | None
    avatar: str | None
    active: bool
    admin: bool
    invited: bool
    groupIds: list[str]
    lastSignInAt: dt.datetime | None
    reactivationAskedAt: dt.datetime | None
    createdAt: dt.datetime
    version: int


class NewUser(Model):
    displayName: str
    username: str
    email: str
    groupIds: list[str] = Field(default_factory=list)


class UserChange(Model):
    displayName: str | None = None
    email: str | None = None
    active: bool | None = None
    groupIds: list[str] | None = None


class GroupRow(Model):
    id: str
    name: str
    active: bool
    builtIn: str | None
    memberIds: list[str]
    createdAt: dt.datetime
    version: int


class NewGroup(Model):
    name: str
    memberIds: list[str] = Field(default_factory=list)


class GroupChange(Model):
    name: str | None = None
    active: bool | None = None
    memberIds: list[str] | None = None


def user_row(s, u: User) -> UserRow:
    return UserRow(
        id=u.id,
        username=u.username,
        displayName=u.displayName,
        email=u.email,
        avatar=u.avatar,
        active=u.active,
        admin=accounts.is_admin(s, u.id),
        invited=u.passwordHash is None and not u.needsSetup,
        groupIds=accounts.group_ids(s, u.id),
        lastSignInAt=u.lastSignInAt,
        reactivationAskedAt=u.reactivationAskedAt,
        createdAt=u.createdAt,
        version=u.version,
    )


def group_row(s, g: Group) -> GroupRow:
    return GroupRow(
        id=g.id,
        name=g.name,
        active=g.active,
        builtIn=g.builtIn,
        memberIds=accounts.members(s, g.id),
        createdAt=g.createdAt,
        version=g.version,
    )


def _user(s, user_id: str) -> User:
    u = s.get(User, user_id)
    if u is None or u.deleted:
        raise Problem(404, "not-found", "Not found")
    return u


def _group(s, group_id: str) -> Group:
    g = s.get(Group, group_id)
    if g is None or g.deleted:
        raise Problem(404, "not-found", "Not found")
    return g


@router.get("/users", response_model=list[UserRow])
def list_users(request: Request, c: Caller = Depends(admin)):
    with server(request).db.read() as s:
        users = s.scalars(
            select(User).where(User.deleted == false()).order_by(User.displayName)
        ).all()
        return [user_row(s, u) for u in users]


@router.post("/users", response_model=UserRow, status_code=201)
def create_user(body: NewUser, request: Request, c: Caller = Depends(admin)):
    srv = server(request)
    with srv.db.tx() as s:
        u = accounts.invite(
            s, srv.services, c.user, body.displayName, body.username, body.email, body.groupIds
        )
        row = user_row(s, u)
    return JSONResponse(
        row.model_dump(mode="json"), status_code=201, headers={"Location": f"/ui/api/users/{u.id}"}
    )


@router.patch("/users/{user_id}", response_model=UserRow)
def change_user(
    user_id: str,
    body: UserChange,
    request: Request,
    c: Caller = Depends(admin),
    version: int = Depends(if_match),
):
    srv = server(request)
    ended: list[str] = []
    with srv.db.tx() as s:
        u = _user(s, user_id)
        if u.version != version:
            raise stale(user_row(s, u))
        accounts.update_user(s, c.user, u, body.displayName, body.email)
        if body.groupIds is not None:
            accounts.set_user_groups(s, c.user, u, body.groupIds)
        if body.active is not None:
            ended = accounts.set_active(s, srv.services, c.user, u, body.active)
        s.flush()
        row = user_row(s, u)
    if ended:
        srv.events.end_user(u.id, "disabled")
    return row


@router.post("/users/{user_id}/invitation", status_code=204)
def resend(user_id: str, request: Request, c: Caller = Depends(admin)):
    srv = server(request)
    with srv.db.tx() as s:
        accounts.resend_invitation(s, srv.services, c.user, _user(s, user_id))
    return Response(status_code=204)


@router.get("/groups", response_model=list[GroupRow])
def list_groups(request: Request, c: Caller = Depends(admin)):
    with server(request).db.read() as s:
        groups = s.scalars(select(Group).where(Group.deleted == false()).order_by(Group.name)).all()
        return [group_row(s, g) for g in groups]


@router.post("/groups", response_model=GroupRow, status_code=201)
def create_group(body: NewGroup, request: Request, c: Caller = Depends(admin)):
    with server(request).db.tx() as s:
        g = accounts.create_group(s, c.user, body.name, body.memberIds)
        row = group_row(s, g)
    return JSONResponse(
        row.model_dump(mode="json"), status_code=201, headers={"Location": f"/ui/api/groups/{g.id}"}
    )


@router.patch("/groups/{group_id}", response_model=GroupRow)
def change_group(
    group_id: str,
    body: GroupChange,
    request: Request,
    c: Caller = Depends(admin),
    version: int = Depends(if_match),
):
    with server(request).db.tx() as s:
        g = _group(s, group_id)
        if g.version != version:
            raise stale(group_row(s, g))
        accounts.update_group(s, c.user, g, body.name, body.active, body.memberIds)
        s.flush()
        return group_row(s, g)
