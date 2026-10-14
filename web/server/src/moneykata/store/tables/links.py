"""Linked servers (requirements S11.1, S11.7): each link with another MoneyKata server."""

from sqlalchemy import CheckConstraint, Column, ForeignKey, Integer, Text

from ..types import UtcTimestamp
from ._base import record, unique_live

# A link with another server (S11.1). On the inviting side it starts as an invitation (its
# code kept as a hash), becomes a request when the other side answers, and is active once an
# admin approves it; on the joining side it waits for that approval. Paused stops the
# exchanges both ways; ended stays listed, and deletes the copies on both sides.
Link = record(
    "Link",
    "Link",
    Column("state", Text, nullable=False),
    Column("role", Text, nullable=False),  # inviter or joiner
    Column("peerName", Text),  # the peer's server name (S16.1)
    Column("householdName", Text),
    Column("householdAvatar", Text),  # JSON, as the peer sets it
    Column("address", Text),  # the peer's link address
    Column("peerKey", Text),  # its Ed25519 public key, base64url
    Column("codeHash", Text),  # an invitation's code
    Column("codeExpiresAt", UtcTimestamp),
    Column("createdById", Text, ForeignKey("User.id")),
    Column("approvedById", Text, ForeignKey("User.id")),
    Column("approvedAt", UtcTimestamp),
    Column("lastOkAt", UtcTimestamp),  # the last exchange that worked, either way
    Column("lastError", Text),
    Column("failingSince", UtcTimestamp),
    Column("peerVersion", Text),
    Column("peerProtocol", Integer),
    Column("endedAt", UtcTimestamp),
    CheckConstraint(
        "state IN ('invited', 'requested', 'pending', 'active', 'paused', 'ended')", name="state"
    ),
    CheckConstraint("role IN ('inviter', 'joiner')", name="role"),
)
unique_live(Link, "peerKey")
