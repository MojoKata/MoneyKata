"""Linked servers (requirements S11.1, S11.7): each link with another MoneyKata server."""

from sqlalchemy import Boolean, CheckConstraint, Column, ForeignKey, Index, Integer, Text, text

from ..types import UtcTimestamp
from ._base import exception, record, unique_live

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
    # The linked copy's access key (S11.9.2): its public key only, and who made it when. The
    # copy key itself is never stored.
    Column("copyPublicKey", Text),
    Column("copyKeyAt", UtcTimestamp),
    Column("copyKeyById", Text, ForeignKey("User.id")),
    CheckConstraint(
        "state IN ('invited', 'requested', 'pending', 'active', 'paused', 'ended')", name="state"
    ),
    CheckConstraint("role IN ('inviter', 'joiner')", name="role"),
)
unique_live(Link, "peerKey")

# What a link brings in, as the main database knows it while the copy is locked (S11.9.1): each
# shared item's id there, kind, owner's display name, when it was shared and the people here it
# names, never its name or figures. Replaced at each pull: a cache (schema.md §4.4.5).
LinkedItem = exception(
    "LinkedItem",
    "cache: replaced from each pull of the link (§4.4.5)",
    Column("linkId", Text, ForeignKey("Link.id", ondelete="CASCADE"), nullable=False),
    Column("remoteId", Text, nullable=False),
    Column("kind", Text, nullable=False),
    Column("ownerName", Text, nullable=False),
    Column("sharedAt", UtcTimestamp, nullable=False),
    Column("viewers", Text, nullable=False, server_default=text("'[]'")),  # local user ids
    Column("includeReceipts", Boolean, nullable=False, server_default=text("0")),
    Column("createdAt", UtcTimestamp, nullable=False),
    prefix="LItem",
)
Index("ux_LinkedItem_link_remote", LinkedItem.c.linkId, LinkedItem.c.remoteId, unique=True)
