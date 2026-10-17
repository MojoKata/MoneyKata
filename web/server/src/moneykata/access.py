"""Who may see and change what (requirements S10.3–S10.7, S13.8.10).

An item's owner holds it; anyone else holds the higher of a direct share and the shares of
the active groups they belong to. An inactive user holds nothing, whatever is shared with
them. Every read goes through these levels, and something the caller can't see answers 404,
never revealing whether it exists.
"""

from dataclasses import dataclass, field

from sqlalchemy import false, or_, select
from sqlalchemy.orm import Session

from .errors import Problem
from .store.entities.accounts import Account
from .store.entities.sharing import Portfolio, Share
from .store.entities.users import Group, User, UserGroup

RANK = {None: 0, "read": 1, "write": 2, "owner": 3}


def higher(a: str | None, b: str | None) -> str | None:
    return a if RANK[a] >= RANK[b] else b


@dataclass
class Reach:
    """What one user holds through shares: (kind, item id) → level, and through which
    groups."""

    userId: str
    active: bool
    levels: dict[tuple[str, str], str] = field(default_factory=dict)
    via: dict[tuple[str, str], list[str]] = field(default_factory=dict)


def groups_of(s: Session, user_id: str) -> list[str]:
    """The active groups a user is in."""
    return list(
        s.scalars(
            select(UserGroup.groupId)
            .join(Group, Group.id == UserGroup.groupId)
            .where(
                UserGroup.userId == user_id,
                UserGroup.deleted == false(),
                Group.deleted == false(),
                Group.active,
            )
        )
    )


def reach(s: Session, user_id: str) -> Reach:
    user = s.get(User, user_id)
    r = Reach(user_id, bool(user and user.active and not user.deleted))
    if not r.active:
        return r
    groups = groups_of(s, user_id)
    names = {g.id: g.name for g in s.scalars(select(Group).where(Group.id.in_(groups)))}
    for sh in s.scalars(
        select(Share).where(
            Share.deleted == false(), or_(Share.userId == user_id, Share.groupId.in_(groups))
        )
    ):
        key = (sh.kind, sh.itemId)
        r.levels[key] = higher(r.levels.get(key), sh.level)
        if sh.groupId:
            r.via.setdefault(key, []).append(names.get(sh.groupId, ""))
    return r


def level_of(
    s: Session,
    user_id: str,
    kind: str,
    owner_id: str,
    item_id: str,
    deleted: bool,
    r: Reach | None = None,
) -> str | None:
    if deleted:
        return None
    if owner_id == user_id:
        return "owner"
    r = r or reach(s, user_id)
    return r.levels.get((kind, item_id))


def account_level(s: Session, user_id: str, account: Account, r: Reach | None = None) -> str | None:
    return level_of(s, user_id, "account", account.ownerId, account.id, account.deleted, r)


def visible_accounts(s: Session, user_id: str) -> list[tuple[Account, str]]:
    """The accounts the user owns or holds a share of, with the level of each."""
    r = reach(s, user_id)
    shared = [i for (k, i) in r.levels if k == "account"]
    rows = s.scalars(
        select(Account)
        .where(Account.deleted == false(), or_(Account.ownerId == user_id, Account.id.in_(shared)))
        .order_by(Account.name)
    ).all()
    out = []
    for a in rows:
        lvl = account_level(s, user_id, a, r)
        if lvl:
            out.append((a, lvl))
    return out


def account(s: Session, user_id: str, account_id: str, need: str = "read") -> tuple[Account, str]:
    a = s.get(Account, account_id)
    lvl = account_level(s, user_id, a) if a is not None else None
    return a, _require(lvl, need, "account")


def portfolio_level(s: Session, user_id: str, p: Portfolio, r: Reach | None = None) -> str | None:
    return level_of(s, user_id, "portfolio", p.ownerId, p.id, p.deleted, r)


def visible_portfolios(s: Session, user_id: str) -> list[tuple[Portfolio, str]]:
    r = reach(s, user_id)
    shared = [i for (k, i) in r.levels if k == "portfolio"]
    rows = s.scalars(
        select(Portfolio)
        .where(
            Portfolio.deleted == false(),
            or_(Portfolio.ownerId == user_id, Portfolio.id.in_(shared)),
        )
        .order_by(Portfolio.name)
    ).all()
    return [(p, lvl) for p in rows if (lvl := portfolio_level(s, user_id, p, r))]


def portfolio(
    s: Session, user_id: str, portfolio_id: str, need: str = "read"
) -> tuple[Portfolio, str]:
    p = s.get(Portfolio, portfolio_id)
    lvl = portfolio_level(s, user_id, p) if p is not None else None
    return p, _require(lvl, need, "portfolio")


def visible_budgets(s: Session, user_id: str) -> list[tuple]:
    from .store.entities.budgets import Budget

    r = reach(s, user_id)
    shared = [i for (k, i) in r.levels if k == "budget"]
    rows = s.scalars(
        select(Budget)
        .where(Budget.deleted == false(), or_(Budget.ownerId == user_id, Budget.id.in_(shared)))
        .order_by(Budget.name)
    ).all()
    return [
        (b, lvl)
        for b in rows
        if (lvl := level_of(s, user_id, "budget", b.ownerId, b.id, b.deleted, r))
    ]


def budget(s: Session, user_id: str, budget_id: str, need: str = "read"):
    from .store.entities.budgets import Budget

    b = s.get(Budget, budget_id)
    lvl = level_of(s, user_id, "budget", b.ownerId, b.id, b.deleted) if b is not None else None
    return b, _require(lvl, need, "budget")


def _require(level: str | None, need: str, what: str) -> str:
    if level is None:
        raise Problem(404, "not-found", "Not found")
    if RANK[level] < RANK[need]:
        if level == "read":
            raise Problem(403, "share-read-only", f"You can read this {what} but not change it.")
        raise Problem(403, "owner-only", f"Only the {what}'s owner can do this.")
    return level


def holders(s: Session, kind: str, item_id: str, owner_id: str) -> dict[str, str]:
    """Everyone who holds an item, with their level: the owner, and every active user its
    shares reach directly or through an active group."""
    out = {owner_id: "owner"}
    for sh in s.scalars(
        select(Share).where(Share.kind == kind, Share.itemId == item_id, Share.deleted == false())
    ):
        if sh.userId:
            users = [sh.userId]
        else:
            g = s.get(Group, sh.groupId)
            users = (
                []
                if g is None or g.deleted or not g.active
                else list(
                    s.scalars(
                        select(UserGroup.userId).where(
                            UserGroup.groupId == g.id, UserGroup.deleted == false()
                        )
                    )
                )
            )
        for uid in users:
            u = s.get(User, uid)
            if u is not None and u.active and not u.deleted and uid != owner_id:
                out[uid] = higher(out.get(uid), sh.level)
    return out
