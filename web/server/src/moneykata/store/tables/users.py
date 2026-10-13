"""Users, groups, sessions and one-time tokens (requirements S10.1, S13.7.1)."""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Integer,
    PrimaryKeyConstraint,
    Text,
    text,
)

from ..types import UtcTimestamp
from ._base import exception, pairs, record, unique_live

User = record(
    "User",
    "User",
    Column("username", Text, nullable=False),
    Column("displayName", Text, nullable=False),
    Column("email", Text),
    Column("active", Boolean, nullable=False, server_default=text("1")),
    # A password is set from an invitation or the default admin's setup; until then, none.
    Column("passwordHash", Text),
    Column("passwordChangedAt", UtcTimestamp),
    # The default admin's first sign-in leads only to the setup step (S10.1.2).
    Column("needsSetup", Boolean, nullable=False, server_default=text("0")),
    Column("avatar", Text),
    Column("timeZone", Text, nullable=False, server_default=text("'auto'")),
    Column("theme", Text, nullable=False, server_default=text("'dark'")),
    Column("birthYear", Integer),
    Column("spouseId", Text, ForeignKey("User.id")),
    Column("alertEmails", Text, nullable=False, server_default=text("'daily'")),
    Column("lastSignInAt", UtcTimestamp),
    Column("reactivationAskedAt", UtcTimestamp),
    CheckConstraint("theme IN ('dark', 'light', 'system')", name="theme"),
    CheckConstraint("\"alertEmails\" IN ('each', 'daily', 'none')", name="alert_emails"),
)
unique_live(User, "username")
unique_live(User, "email")

Group = record(
    "Group",
    "Group",
    Column("name", Text, nullable=False),
    Column("active", Boolean, nullable=False, server_default=text("1")),
    # The built-in Admins group: membership is what makes an admin (S10.1.8).
    Column("builtIn", Text),
    CheckConstraint('"builtIn" IS NULL OR "builtIn" = \'admins\'', name="built_in"),
)
unique_live(Group, "name")

UserGroups = pairs(
    "UserGroups",
    Column("userId", Text, ForeignKey("User.id", ondelete="CASCADE"), nullable=False),
    Column("groupId", Text, ForeignKey("Group.id", ondelete="CASCADE"), nullable=False),
    PrimaryKeyConstraint("userId", "groupId"),
)

Session = exception(
    "Session",
    "sessions are removed when they end or expire (§4.4.1)",
    Column("tokenHash", Text, primary_key=True),
    Column("userId", Text, ForeignKey("User.id"), nullable=False),
    Column("createdAt", UtcTimestamp, nullable=False),
    Column("lastSeenAt", UtcTimestamp, nullable=False),
    Column("expiresAt", UtcTimestamp, nullable=False),
    # When the password was last given in this session, for re-authentication (S13.7.2).
    Column("authAt", UtcTimestamp, nullable=False),
    Column("admin", Boolean, nullable=False, server_default=text("0")),
    Column("needsSetup", Boolean, nullable=False, server_default=text("0")),
    Index("ix_Session_userId", "userId"),
)

OneTimeToken = exception(
    "OneTimeToken",
    "one-time tokens are removed when used or expired (§4.4.1)",
    Column("tokenHash", Text, primary_key=True),
    Column("purpose", Text, nullable=False),
    Column("userId", Text, ForeignKey("User.id"), nullable=False),
    Column("data", Text),
    Column("createdAt", UtcTimestamp, nullable=False),
    Column("expiresAt", UtcTimestamp, nullable=False),
    CheckConstraint("purpose IN ('invitation', 'reset', 'email-change')", name="purpose"),
    Index("ix_OneTimeToken_userId", "userId"),
)
