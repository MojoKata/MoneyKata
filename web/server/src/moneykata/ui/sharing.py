"""The Share dialog and a receiver's Count in my totals (requirements S10.4–S10.7)."""

from typing import Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from pydantic import Field
from sqlalchemy import false, select

from .. import access, clock, sharing
from ..errors import Problem
from ..store.entities.accounts import Account
from ..store.entities.sharing import CountedAccount
from ..store.entities.users import Group, User, UserGroup
from .conventions import ExactRoute, Model
from .deps import Caller, caller, server

router = APIRouter(prefix="/ui/api", route_class=ExactRoute, tags=["sharing"])
Kind = Literal["account", "portfolio", "budget", "projection", "person", "giving-plan", "tax-book"]


class Via(Model):
    groupId: str
    groupName: str
    level: str


class UserGrant(Model):
    id: str
    displayName: str
    avatar: str | None
    level: str
    via: list[Via]


class GroupGrant(Model):
    id: str
    name: str
    level: str
    members: int


class AccountName(Model):
    id: str
    name: str
    yours: bool


class LinkedPeople(Model):
    linkId: str
    serverName: str
    householdName: str | None
    includeReceipts: bool
    users: list[UserGrant]


class ShareView(Model):
    kind: str
    itemId: str
    itemName: str
    users: list[UserGrant]
    groups: list[GroupGrant]
    links: list[LinkedPeople]
    hidden: dict[str, list[str]]
    accounts: list[AccountName]


class ShareSave(Model):
    users: dict[str, str] = Field(default_factory=dict)
    groups: dict[str, str] = Field(default_factory=dict)
    shareAccountsToo: bool = False
    receipts: dict[str, bool] = Field(default_factory=dict)  # by link: Include receipts


class Saved(Model):
    view: ShareView
    alsoShared: int


class Counted(Model):
    counted: bool


def view(s, owner: User, kind: str, item_id: str) -> ShareView:
    obj = sharing.item(s, kind, item_id)
    current = sharing.grants(s, kind, item_id)
    direct = {g.userId: g.level for g in current if g.userId}
    by_group = {g.groupId: g.level for g in current if g.groupId}
    groups = s.scalars(
        select(Group).where(Group.deleted == false(), Group.active).order_by(Group.name)
    ).all()
    members: dict[str, list[str]] = {}
    for m in s.scalars(select(UserGroup).where(UserGroup.deleted == false())):
        members.setdefault(m.groupId, []).append(m.userId)
    users = s.scalars(
        select(User)
        .where(User.deleted == false(), User.active, User.id != owner.id, User.linkId.is_(None))
        .order_by(User.displayName)
    ).all()
    out_users = []
    for u in users:
        via = [
            Via(groupId=g.id, groupName=g.name, level=by_group[g.id])
            for g in groups
            if g.id in by_group and u.id in members.get(g.id, [])
        ]
        out_users.append(
            UserGrant(
                id=u.id,
                displayName=u.displayName,
                avatar=u.avatar,
                level=direct.get(u.id, "none"),
                via=via,
            )
        )
    hidden: dict[str, list[str]] = {}
    accounts: list[AccountName] = []
    if kind == "portfolio":
        people = [u for u in access.holders(s, kind, item_id, obj.ownerId) if u != owner.id]
        hidden = sharing.hidden_accounts(s, obj, people)
        accounts = [
            AccountName(id=a.id, name=a.name, yours=a.ownerId == owner.id)
            for a in sharing.portfolio_accounts(s, item_id)
        ]
    return ShareView(
        kind=kind,
        itemId=item_id,
        itemName=obj.name,
        links=_linked(s, current),
        users=out_users,
        groups=[
            GroupGrant(
                id=g.id,
                name=g.name,
                level=by_group.get(g.id, "none"),
                members=len(members.get(g.id, [])),
            )
            for g in groups
        ],
        hidden=hidden,
        accounts=accounts,
    )


def _linked(s, current) -> list[LinkedPeople]:
    """Each live link's people (S10.4): None or Read, with Include receipts per server."""
    from ..store.entities.links import Link

    direct = {g.userId: g for g in current if g.userId}
    out = []
    for link in s.scalars(
        select(Link)
        .where(Link.deleted == false(), Link.state.in_(("active", "paused")))
        .order_by(Link.peerName)
    ):
        people = s.scalars(
            select(User)
            .where(User.linkId == link.id, User.deleted == false(), User.active)
            .order_by(User.displayName)
        ).all()
        if not people:
            continue
        out.append(
            LinkedPeople(
                linkId=link.id,
                serverName=link.peerName or "a linked server",
                householdName=link.householdName,
                includeReceipts=any(direct[u.id].includeReceipts for u in people if u.id in direct),
                users=[
                    UserGrant(
                        id=u.id,
                        displayName=u.displayName,
                        avatar=None,
                        level=direct[u.id].level if u.id in direct else "none",
                        via=[],
                    )
                    for u in people
                ],
            )
        )
    return out


def _owner_only(s, c: Caller, kind: str, item_id: str) -> None:
    obj = sharing.item(s, kind, item_id)
    lvl = access.level_of(s, c.id, kind, obj.ownerId, obj.id, obj.deleted)
    if lvl is None:
        raise Problem(404, "not-found", "Not found")
    if lvl != "owner":
        raise Problem(403, "owner-only", "Only the owner changes who this is shared with.")


@router.get("/shares/{kind}/{item_id}", response_model=ShareView)
def get_shares(kind: Kind, item_id: str, request: Request, c: Caller = Depends(caller)):
    with server(request).db.read() as s:
        _owner_only(s, c, kind, item_id)
        return view(s, c.user, kind, item_id)


@router.put("/shares/{kind}/{item_id}", response_model=Saved)
def save_shares(
    kind: Kind, item_id: str, body: ShareSave, request: Request, c: Caller = Depends(caller)
):
    """Save: the dialog's grants replace the item's (S10.4)."""
    srv = server(request)
    with srv.db.tx() as s:
        _owner_only(s, c, kind, item_id)
        change = sharing.save(
            s,
            c.user,
            kind,
            item_id,
            body.users,
            body.groups,
            body.shareAccountsToo,
            body.receipts,
        )
        s.flush()
        out = Saved(view=view(s, c.user, kind, item_id), alsoShared=change.alsoShared)
    if change.affected:
        srv.events.publish("share", {"kind": kind}, users=change.affected)
    return out


@router.put("/accounts/{account_id}/counted", status_code=204)
def set_counted(account_id: str, body: Counted, request: Request, c: Caller = Depends(caller)):
    """A receiver's Count in my totals (S10.7); off by default."""
    with server(request).db.tx() as s:
        a, level = access.account(s, c.id, account_id)
        if level == "owner":
            raise Problem(
                409, "owner-counts", "Your own accounts count by their Count in net worth setting."
            )
        row = s.get(CountedAccount, (c.id, a.id))
        if row is None:
            s.add(
                CountedAccount(
                    userId=c.id,
                    accountId=a.id,
                    counted=body.counted,
                    createdAt=clock.now(),
                )
            )
        else:
            row.counted = body.counted
    return Response(status_code=204)


def counted_for(s, user_id: str) -> set[str]:
    return set(
        s.scalars(
            select(CountedAccount.accountId).where(
                CountedAccount.userId == user_id,
                CountedAccount.counted,
                CountedAccount.deleted == false(),
            )
        )
    )


def shared_counts(s, owner_id: str) -> dict[str, int]:
    """How many people hold each of an owner's accounts besides the owner."""
    out = {}
    for a in s.scalars(
        select(Account).where(Account.ownerId == owner_id, Account.deleted == false())
    ):
        out[a.id] = len(access.holders(s, "account", a.id, owner_id)) - 1
    return out
