"""The MoneyKata Connector's side on the server (requirements S18, docs/connector-protocol.md):
the `/connector/v1/` listener, pairing, reports, credentials and file posts. MoneyKata holds the
connector's public keys and these records, never a credential."""

PROTOCOL = 1
SUPPORTED = (1,)
