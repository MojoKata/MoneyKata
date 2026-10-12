"""Dev mode's shares and portfolios (requirements §20.7), so every sharing mark shows."""

import datetime as dt

from sqlalchemy import func, select

from .. import activity, ids
from ..store.entities.accounts import Account, Import, Transaction
from ..store.entities.sharing import CountedAccount, Portfolio, PortfolioAccount, Share
from ..store.entities.users import Group


def seed_sharing(s, people: dict) -> None:
    alice, bob = people["alice"], people["bob"]
    acct = {a.name: a for a in s.scalars(select(Account))}
    household = s.scalars(select(Group).where(Group.name == "Household")).one()
    now = dt.datetime.now(dt.UTC)

    def grant(kind, item, level, user=None, group=None, by=alice):
        s.add(
            Share(
                id=ids.new_id("Share"),
                kind=kind,
                itemId=item.id,
                level=level,
                userId=user.id if user else None,
                groupId=group.id if group else None,
                createdById=by.id,
            )
        )

    grant("account", acct["Everyday checking"], "read", group=household)
    grant("account", acct["Emergency savings"], "write", user=bob)
    grant("account", acct["Rollover IRA"], "read", user=alice, by=bob)
    s.add(CountedAccount(userId=alice.id, accountId=acct["Rollover IRA"].id, createdAt=now))

    def portfolio(owner, name, names, benchmark="VT"):
        p = Portfolio(id=ids.new_id("Portf"), ownerId=owner.id, name=name, benchmark=benchmark)
        s.add(p)
        s.flush()
        for n in names:
            s.add(PortfolioAccount(portfolioId=p.id, accountId=acct[n].id, createdAt=now))
        return p

    retirement = portfolio(
        alice, "Retirement", ["Roth IRA", "Acme 401(k)", "Health savings"], "60-40"
    )
    portfolio(alice, "Family investing", ["Taxable brokerage", "Roth IRA", "Rollover IRA"], "SPY")
    grant("portfolio", retirement, "read", user=bob)
    s.flush()
    _history(s)


def _history(s) -> None:
    """Activity for what the seed made, so the Activity screen has something to show."""
    for a in s.scalars(select(Account).order_by(Account.createdAt)):
        activity.record(
            s,
            "account.created",
            actor=a.ownerId,
            subject_kind="account",
            subject_id=a.id,
            owner=a.ownerId,
        )
    for i in s.scalars(select(Import).order_by(Import.createdAt)):
        a = s.get(Account, i.accountId)
        added = s.scalar(
            select(func.count()).select_from(Transaction).where(Transaction.importId == i.id)
        )
        activity.record(
            s,
            "account.imported",
            actor=i.userId,
            subject_kind="account",
            subject_id=a.id,
            owner=a.ownerId,
            detail={"added": added, "matched": 0, "changed": 0, "format": i.format},
        )
    for p in s.scalars(select(Portfolio)):
        activity.record(
            s,
            "portfolio.created",
            actor=p.ownerId,
            subject_kind="portfolio",
            subject_id=p.id,
            owner=p.ownerId,
        )
    for sh in s.scalars(select(Share)):
        owner = (s.get(Account, sh.itemId) or s.get(Portfolio, sh.itemId)).ownerId
        activity.record(
            s,
            "share.given",
            actor=sh.createdById,
            subject_kind=sh.kind,
            subject_id=sh.itemId,
            owner=owner,
            detail={
                "granteeKind": "user" if sh.userId else "group",
                "granteeId": sh.userId or sh.groupId,
                "level": sh.level,
            },
        )
