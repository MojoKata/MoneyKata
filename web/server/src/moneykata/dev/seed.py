"""Dev mode's seed data (requirements S17.7): the users admin, alice and bob, a Household
group, and a year of their accounts; each part of the app adds its own."""

import datetime as dt
import logging

from sqlalchemy import select

from .. import clock, ids, settings
from ..auth import passwords
from ..auth import users as accounts
from ..store.entities.alerts import Alert
from ..store.entities.users import Group, User, UserGroup
from .seed_accounts import seed_accounts
from .seed_assets import seed_assets
from .seed_budgets import seed_budgets
from .seed_education import seed_education
from .seed_gifts import seed_gifts
from .seed_giving import seed_giving
from .seed_links import seed_links
from .seed_loans import seed_loans
from .seed_options import seed_options
from .seed_projections import seed_projections
from .seed_receipts import seed_receipts
from .seed_sharing import seed_sharing
from .seed_taxes import seed_taxes
from .seed_wallets import seed_wallets

log = logging.getLogger("moneykata.dev")
PASSWORD = "moneykata-dev"  # noqa: S105 - dev mode's seed users only


def seed(server) -> None:
    with server.db.tx() as s:
        if s.scalars(select(User).where(User.username == "alice")).first():
            log.info("dev: already seeded")
            return
        people = seed_users(s)
        seed_accounts(s, people)
        seed_loans(s, people)
        seed_assets(s, people)
        seed_education(s, people)
        seed_gifts(s, people)
        seed_giving(s, people)
        seed_taxes(s, people)
        seed_options(s, people)
        seed_wallets(s, people)
        seed_links(server, s, people)
        seed_sharing(s, people)
        seed_budgets(s, people)
        seed_receipts(server, s, people)
        seed_projections(s, people)
        seed_alerts(s)
    log.info("dev: seeded; sign in as admin, alice or bob with %r", PASSWORD)
    from .seed_links import words

    log.info("dev: griffin-parents' linked copy opens with: %s", words())


def seed_users(s) -> dict[str, User]:
    settings.put(s, "householdName", "Alice & Bob", None)
    settings.put(
        s, "householdAvatar", {"kind": "initials", "initials": "AB", "color": "#3b7a57"}, None
    )
    admin = s.scalars(select(User).where(User.username == "admin")).one()
    admin.passwordHash = passwords.hash_password(PASSWORD)
    admin.needsSetup = False
    admin.email = "admin@griffin.home"
    people = {"admin": admin}
    for username, name, birth in (("alice", "Alice Griffin", 1979), ("bob", "Bob Griffin", 1977)):
        u = User(
            id=ids.new_id("User"),
            username=username,
            displayName=name,
            email=f"{username}@griffin.home",
            birthYear=birth,
            passwordHash=passwords.hash_password(PASSWORD),
        )
        s.add(u)
        people[username] = u
    s.flush()
    # An admin starts on an email for each alert (S12.11.5).
    people["alice"].alertEmails = "each"
    people["alice"].spouseId, people["bob"].spouseId = people["bob"].id, people["alice"].id
    s.add(
        UserGroup(
            userId=people["alice"].id, groupId=accounts.admins_group(s).id, createdAt=accounts.now()
        )
    )
    household = Group(id=ids.new_id("Group"), name="Household")
    s.add(household)
    s.flush()
    for u in ("alice", "bob"):
        s.add(UserGroup(userId=people[u].id, groupId=household.id, createdAt=accounts.now()))
    return people


def seed_alerts(s) -> None:
    """A resolved alert for the admins; open ones come from the seed's own causes."""

    now = clock.now()
    s.add(
        Alert(
            id=ids.new_id("Alert"),
            kind="backup-failed",
            causeKey="backups",
            title="Backup failed",
            about="the backup directory was full",
            link="/ui/settings/backups",
            fix="Backups",
            seenSince=now - dt.timedelta(days=6),
            openedAt=now - dt.timedelta(days=6),
            resolvedAt=now - dt.timedelta(days=5),
            resolution="the next backup succeeded",
        )
    )
