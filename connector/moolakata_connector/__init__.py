"""The MoolaKata Connector (requirements S18): a second service that keeps institutions'
credentials in a vault of its own, fetches with its drivers, and pushes what they fetch into
MoolaKata's import. Python with the standard library and `cryptography`; nothing from
MoolaKata is imported (S18.1.2). docs/connector-protocol.md states the wire."""

VERSION = "0.1.0"
PROTOCOL = 1
