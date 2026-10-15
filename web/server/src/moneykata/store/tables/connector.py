"""The MoneyKata Connector (requirements S18): the one connector paired with this server, and
each user's Connections, the sign-ins it keeps for them. MoneyKata holds the connector's public
keys and these records, never a credential (S18.2.3)."""

from sqlalchemy import Boolean, CheckConstraint, Column, ForeignKey, Integer, Text, text

from ..types import UtcTimestamp
from ._base import record, unique_live

# The paired connector (S18.4). One is paired at a time: pairing another replaces it, as
# Unpair does, and the replaced one ends (endedAt). While a pairing code is out, the row holds
# the code's secret as a hash until the connector introduces itself with it.
Connector = record(
    "Connector",
    "Cnctr",
    Column("state", Text, nullable=False),  # pairing, paired, ended
    Column("codeHash", Text),  # the one-time pairing code's secret (S18.4.1)
    Column("codeExpiresAt", UtcTimestamp),
    Column("identityKey", Text),  # its Ed25519 public key, base64url (S18.4.2)
    Column("sealingKey", Text),  # its X25519 public key, base64url (S18.7.1)
    Column("pairedAt", UtcTimestamp),
    Column("pairedById", Text, ForeignKey("User.id")),
    Column("endedAt", UtcTimestamp),  # unpaired, or replaced by another pairing
    Column("endedById", Text, ForeignKey("User.id")),
    # Its reports (S18.5): the last one, whether it said it was locked, and what it runs.
    Column("lastReportAt", UtcTimestamp),
    Column("locked", Boolean, nullable=False, server_default=text("1")),
    Column("connectorVersion", Text),  # the connector's own version, from its reports
    Column("protocol", Integer),
    CheckConstraint("state IN ('pairing', 'paired', 'ended')", name="state"),
)
unique_live(Connector, "identityKey")

# A Connection (S18.6): one sign-in at one institution, kept by the connector and owned by
# the user whose sign-in it is. Its state and last run come from the connector's reports; the
# institution accounts the driver found are kept as JSON (name and last four digits). A
# credential sealed for the connector (S18.7.1) waits here only as ciphertext MoneyKata can't
# open, until the connector collects it.
Connection = record(
    "Connection",
    "Conn",
    Column("ownerId", Text, ForeignKey("User.id", ondelete="CASCADE"), nullable=False),
    Column("connectorId", Text, ForeignKey("Connector.id"), nullable=False),
    Column("driver", Text, nullable=False),  # folder, ofx-direct, schwab
    Column("label", Text, nullable=False),  # "Alice's Schwab login"
    Column("state", Text, nullable=False),  # new, ok, needs-sign-in, failing, removed
    Column("message", Text),  # the connector's words for the state
    Column("lastRunAt", UtcTimestamp),
    Column("lastRunAdded", Integer),  # what the last run posted, as the connector counts it
    Column("institutionAccounts", Text, nullable=False, server_default=text("'[]'")),
    Column("settings", Text, nullable=False, server_default=text("'{}'")),  # the driver's own
    Column("sealedCredential", Text),  # waiting for the connector, base64url; deleted once taken
    Column("sealedAt", UtcTimestamp),
    Column("signInAddress", Text),  # an OAuth sign-in the connector reported (S18.7.1)
    Column("removedAt", UtcTimestamp),  # Remove (S18.6.4): the connector deletes its credentials
    CheckConstraint("state IN ('new', 'ok', 'needs-sign-in', 'failing', 'removed')", name="state"),
    CheckConstraint("driver IN ('folder', 'ofx-direct', 'schwab')", name="driver"),
)
unique_live(Connection, "ownerId", "label")
