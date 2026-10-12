"""Who may see and change what (requirements §13.3, §16.8.10). Every read goes through the
caller's level on the item: owner, write or read. Something the caller can't see answers 404,
never revealing whether it exists."""

from sqlalchemy import false, select
from sqlalchemy.orm import Session

from .errors import Problem
from .store.entities.accounts import Account

RANK = {None: 0, "read": 1, "write": 2, "owner": 3}


def account_level(s: Session, user_id: str, account: Account) -> str | None:
    if account.deleted:
        return None
    if account.ownerId == user_id:
        return "owner"
    return None


def visible_accounts(s: Session, user_id: str) -> list[tuple[Account, str]]:
    """The accounts the user owns or holds a share of, with the level of each."""
    rows = s.scalars(select(Account).where(Account.deleted == false()).order_by(Account.name)).all()
    out = []
    for a in rows:
        level = account_level(s, user_id, a)
        if level:
            out.append((a, level))
    return out


def account(s: Session, user_id: str, account_id: str, need: str = "read") -> tuple[Account, str]:
    a = s.get(Account, account_id)
    level = account_level(s, user_id, a) if a is not None else None
    if level is None:
        raise Problem(404, "not-found", "Not found")
    if RANK[level] < RANK[need]:
        raise Problem(
            403,
            "share-read-only" if level == "read" else "owner-only",
            "You can read this account but not change it."
            if level == "read"
            else "Only the account's owner can do this.",
        )
    return a, level
