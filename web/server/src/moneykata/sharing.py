"""Sharing an account or a portfolio with users and groups (requirements S10.3–S10.6, S5.1).

The Share dialog lists every active user and group with None, Read or Write; nothing changes
until Save, which replaces the item's grants as a whole. Removing a share ends the receiver's
access on their next request and deletes their own annotations on the item (their tags).
"""

from dataclasses import dataclass, field

from sqlalchemy import false, select
from sqlalchemy.orm import Session

from . import access, activity, clock, ids
from .errors import FieldError, Problem
from .store.entities.accounts import Account, Transaction, TransactionTag
from .store.entities.sharing import Portfolio, PortfolioAccount, Share
from .store.entities.users import Group, User

LEVELS = ("none", "read", "write")


def item(s: Session, kind: str, item_id: str):
    from .store.entities.budgets import Budget
    from .store.entities.education import Person
    from .store.entities.giving import GivingPlan
    from .store.entities.projections import Projection
    from .store.entities.taxes import TaxBook

    cls = {
        "account": Account,
        "portfolio": Portfolio,
        "budget": Budget,
        "projection": Projection,
        "person": Person,
        "giving-plan": GivingPlan,
        "tax-book": TaxBook,
    }.get(kind)
    if cls is None:
        raise Problem(404, "not-found", "Not found")
    obj = s.get(cls, item_id)
    if obj is None or obj.deleted:
        raise Problem(404, "not-found", "Not found")
    return obj


def grants(s: Session, kind: str, item_id: str) -> list[Share]:
    return list(
        s.scalars(
            select(Share).where(
                Share.kind == kind, Share.itemId == item_id, Share.deleted == false()
            )
        )
    )


def portfolio_accounts(s: Session, portfolio_id: str) -> list[Account]:
    return list(
        s.scalars(
            select(Account)
            .join(PortfolioAccount, PortfolioAccount.accountId == Account.id)
            .where(
                PortfolioAccount.portfolioId == portfolio_id,
                PortfolioAccount.deleted == false(),
                Account.deleted == false(),
            )
            .order_by(Account.name)
        )
    )


def hidden_accounts(s: Session, p: Portfolio, user_ids: list[str]) -> dict[str, list[str]]:
    """For each person, the portfolio's accounts they can't see (S5.1.2)."""
    accounts = portfolio_accounts(s, p.id)
    out = {}
    for uid in user_ids:
        r = access.reach(s, uid)
        missing = [a.id for a in accounts if not access.account_level(s, uid, a, r)]
        if missing:
            out[uid] = missing
    return out


@dataclass
class Change:
    added: list[tuple[str, str, str]] = field(default_factory=list)  # (kind, id, level)
    changed: list[tuple[str, str, str]] = field(default_factory=list)
    removed: list[tuple[str, str]] = field(default_factory=list)
    affected: set[str] = field(default_factory=set)
    alsoShared: int = 0


def save(
    s: Session,
    by: User,
    kind: str,
    item_id: str,
    users: dict[str, str],
    groups: dict[str, str],
    share_accounts_too: bool = False,
    receipts: dict[str, bool] | None = None,
) -> Change:
    obj = item(s, kind, item_id)
    if obj.ownerId != by.id:
        raise Problem(403, "owner-only", "Only the owner changes who this is shared with.")
    errors: list[FieldError] = []
    for uid, lvl in users.items():
        u = s.get(User, uid)
        if lvl not in LEVELS:
            errors.append(FieldError(f"users.{uid}", "level-invalid", "None, Read or Write."))
        elif u is None or u.deleted or uid == by.id:
            errors.append(FieldError(f"users.{uid}", "user-unknown", "Choose a user."))
        elif u.linkId and lvl == "write":
            errors.append(
                FieldError(
                    f"users.{uid}",
                    "read-only",
                    f"{u.displayName} is on a linked server: shares there are read only.",
                )
            )
        elif u.linkId and lvl != "none" and not _link_live(s, u.linkId):
            errors.append(
                FieldError(f"users.{uid}", "link-not-active", "That server's link isn't active.")
            )
        elif lvl != "none" and not u.active:
            errors.append(
                FieldError(
                    f"users.{uid}",
                    "user-inactive",
                    f"{u.displayName} is not active and can't be added.",
                )
            )
    for gid, lvl in groups.items():
        g = s.get(Group, gid)
        if lvl not in LEVELS:
            errors.append(FieldError(f"groups.{gid}", "level-invalid", "None, Read or Write."))
        elif g is None or g.deleted:
            errors.append(FieldError(f"groups.{gid}", "group-unknown", "Choose a group."))
        elif lvl != "none" and not g.active:
            errors.append(
                FieldError(
                    f"groups.{gid}", "group-inactive", f"{g.name} is not active and can't be added."
                )
            )
    if errors:
        raise Problem(422, errors[0].code, errors[0].message, errors)

    before = access.holders(s, kind, item_id, obj.ownerId)
    current = {
        ("user", g.userId) if g.userId else ("group", g.groupId): g
        for g in grants(s, kind, item_id)
    }
    change = Change()
    wanted = {("user", k): v for k, v in users.items()} | {
        ("group", k): v for k, v in groups.items()
    }
    for (gk, gid), lvl in wanted.items():
        row = current.get((gk, gid))
        if lvl == "none":
            if row is not None:
                row.mark_deleted(by.id)
                change.removed.append((gk, gid))
        elif row is None:
            s.add(
                Share(
                    id=ids.new_id("Share"),
                    kind=kind,
                    itemId=item_id,
                    level=lvl,
                    userId=gid if gk == "user" else None,
                    groupId=gid if gk == "group" else None,
                    createdById=by.id,
                )
            )
            change.added.append((gk, gid, lvl))
        elif row.level != lvl:
            row.level = lvl
            change.changed.append((gk, gid, lvl))
    s.flush()
    _set_receipts(s, kind, item_id, receipts or {})

    if kind == "portfolio" and share_accounts_too:
        change.alsoShared = _share_accounts_too(s, by, obj)
    after = access.holders(s, kind, item_id, obj.ownerId)
    lost = [u for u in before if u not in after]
    if kind == "account":
        for uid in lost:
            _drop_annotations(s, uid, item_id)
    change.affected = set(before) ^ set(after) | {u for u in after if after[u] != before.get(u)}
    change.affected.discard(obj.ownerId)
    for gk, gid, lvl in change.added + change.changed:
        activity.record(
            s,
            "share.given" if (gk, gid, lvl) in change.added else "share.changed",
            actor=by.id,
            subject_kind=kind,
            subject_id=item_id,
            owner=obj.ownerId,
            detail={"granteeKind": gk, "granteeId": gid, "level": lvl},
        )
    for gk, gid in change.removed:
        activity.record(
            s,
            "share.removed",
            actor=by.id,
            subject_kind=kind,
            subject_id=item_id,
            owner=obj.ownerId,
            detail={"granteeKind": gk, "granteeId": gid},
        )
    return change


def _share_accounts_too(s: Session, by: User, p: Portfolio) -> int:
    """Share these accounts too (S5.1.2): at read, only accounts the owner may share."""
    n = 0
    people = [u for u in access.holders(s, "portfolio", p.id, p.ownerId) if u != p.ownerId]
    for uid, missing in hidden_accounts(s, p, people).items():
        for aid in missing:
            a = s.get(Account, aid)
            if a.ownerId != by.id:
                continue
            s.add(
                Share(
                    id=ids.new_id("Share"),
                    kind="account",
                    itemId=aid,
                    level="read",
                    userId=uid,
                    createdById=by.id,
                )
            )
            activity.record(
                s,
                "share.given",
                actor=by.id,
                subject_kind="account",
                subject_id=aid,
                owner=a.ownerId,
                detail={"granteeKind": "user", "granteeId": uid, "level": "read"},
            )
            n += 1
    s.flush()
    return n


def _drop_annotations(s: Session, user_id: str, account_id: str) -> None:
    """A removed receiver's own tags on the account's transactions are deleted (S10.4)."""
    now = clock.now()
    for tag in s.scalars(
        select(TransactionTag)
        .join(Transaction, Transaction.id == TransactionTag.transactionId)
        .where(
            Transaction.accountId == account_id,
            TransactionTag.userId == user_id,
            TransactionTag.deleted == false(),
        )
    ):
        tag.deleted, tag.deletedAt, tag.deletedById = True, now, user_id


def _link_live(s: Session, link_id: str) -> bool:
    from .store.entities.links import Link

    link = s.get(Link, link_id)
    return link is not None and not link.deleted and link.state in ("active", "paused")


def _set_receipts(s: Session, kind: str, item_id: str, receipts: dict[str, bool]) -> None:
    """Include receipts, per linked server (S11.5.1): the same on each share with its users."""
    if not receipts:
        return
    for g in grants(s, kind, item_id):
        if not g.userId:
            continue
        u = s.get(User, g.userId)
        if u is not None and u.linkId in receipts:
            g.includeReceipts = bool(receipts[u.linkId])
    s.flush()


def remove_link_shares(s: Session, link_id: str, by: str | None = None) -> int:
    """When a link ends, the shares naming its users go (S10.3.3)."""
    ids_ = [u.id for u in s.scalars(select(User).where(User.linkId == link_id))]
    if not ids_:
        return 0
    n = 0
    for row in s.scalars(select(Share).where(Share.userId.in_(ids_), Share.deleted == false())):
        row.mark_deleted(by)
        n += 1
    return n
