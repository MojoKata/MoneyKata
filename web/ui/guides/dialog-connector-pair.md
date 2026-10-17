# Pair a connector

## Pairing command {#pairing-command}

Run it on the connector's host within 24 hours. The code in it holds this server's address, its
key's fingerprint and a one-time secret; it works once. The connector checks the fingerprint
before it sends anything, makes its own keys if it has none, and introduces itself. Both sides
then show the connector's fingerprint: compare them before trusting it. Pairing another
connector replaces the one paired, as Unpair does.
