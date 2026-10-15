# The connector protocol

How the MoneyKata Connector talks to the MoneyKata server it is paired with (requirements
S18). This document is the protocol's statement; the code that speaks it is
`web/server/src/moneykata/connector/` on the server's side and `connector/core/` on the
connector's. It follows the link protocol (`link-protocol.md`) wherever the two do the same
thing, so one reading covers both.

## 1. Transport

1. The connector **only opens connections** (S18.2.2): HTTPS POSTs of JSON, or multipart for a
   file, to `/connector/v1/` on MoneyKata's address, the one in the pairing code. MoneyKata
   never calls the connector; everything the connector must learn comes back in the answers
   to its own calls.
2. MoneyKata's TLS certificate may be its own (S13.3): what proves who answered is the
   signature on the answer (section 3), checked against the link key whose fingerprint the
   pairing code carried.
3. Everything but `hello` is signed, and every answer to a signed call is signed back.
4. JSON bodies are UTF-8, at most 1 MB; a file post is multipart, the file up to the upload
   size in Settings (S13.7.6).
5. Only addresses in Settings › Network's **Allowed to connect** ranges reach `/connector`
   (S16.14); others get 404, as for `/ui`.

## 2. Keys and fingerprints

1. The connector has two keys, made at pairing and kept beside its vault, not in it (S18.4.5):
   an **identity key** (Ed25519) that signs its calls, and a **sealing key** (X25519) that
   credentials are sealed to (S18.7.1). MoneyKata holds only their public halves.
2. MoneyKata signs its answers with its **link key** (`link-protocol.md` §2), the same key
   its peers know; a server without a link yet makes it at the first pairing.
3. A key's **fingerprint** is the SHA-256 of its raw 32-byte public key, in hex. The pairing
   code carries MoneyKata's whole; screens show the first 16 digits in four groups for the
   admin to compare (`c2f1 08aa 5e7d 91b3`).
4. Keys travel as their raw 32 bytes in unpadded base64url.

## 3. Signed calls

1. A call carries these headers:

   | Header | Value |
   |---|---|
   | `MK-Conn-Key` | the connector's identity public key |
   | `MK-Conn-Time` | Unix seconds |
   | `MK-Conn-Nonce` | 16 random bytes, base64url |
   | `MK-Conn-Signature` | Ed25519 over the lines below, base64url |
   | `MK-Conn-Protocol` | the protocol version the call speaks (section 7) |
   | `MK-Conn-Version` | the connector's version, for Settings › Connector to show |

   The signed text is these lines, joined by `\n`:

   ```
   MK-CONN-1
   <method, upper case>
   <path with its query>
   <SHA-256 of the body, hex>
   <time>
   <nonce>
   <MoneyKata's link-key fingerprint>
   ```

   For a multipart post the body hash is over the raw request body as sent. Naming the
   receiver's fingerprint means a call can't be replayed against another server.
2. MoneyKata refuses, with the codes in section 8: a call without these headers, a time more
   than **60 seconds** from its own clock, a signature that doesn't verify, a nonce it has
   seen from that key in the last two minutes, a key that isn't the paired connector's, and a
   paired connector whose pairing has ended.
3. **Answers** are signed the same way: `MK-Conn-Time` and `MK-Conn-Signature` over

   ```
   MK-CONN-1-ANSWER
   <HTTP status>
   <SHA-256 of the body, hex>
   <time>
   <the call's nonce>
   ```

   The connector refuses an answer that isn't signed by the key the pairing code named, so a
   server pretending to be MoneyKata gets nothing past it: no report, no file, and no sealed
   credential is ever sent to it. Refusals are signed too when the call carried a nonce.
4. Rate: 60 calls a minute (S13.7.5.4); a file post also counts against the upload limit of the
   Connection's owner (S18.8).

## 4. Calls

| Path | Signed | What it does |
|---|---|---|
| `GET /connector/v1/hello` | no | `{protocol, version, fingerprint}`: lets a connector check the fingerprint in a pairing code before it sends anything |
| `POST /connector/v1/pair` | by the connector's new identity key | introduces the connector with a pairing code (section 4.1) |
| `POST /connector/v1/report` | yes | the connector's state every 5 minutes, answered with the work waiting (section 4.2) |
| `POST /connector/v1/connections/{id}/credential/taken` | yes | the sealed credential was filed in the vault: MoneyKata deletes its copy (section 4.3) |
| `POST /connector/v1/connections/{id}/sign-in` | yes | a driver needs the owner to sign in at the institution's page: the address to open (section 4.3) |
| `POST /connector/v1/accounts/{id}/files` | yes | a driver posts a file for one account (section 4.4) |
| `POST /connector/v1/unpaired` | yes | the connector was told to forget this server (`moneykata-connector unpair`): MoneyKata ends the pairing as Unpair would |

### 4.1 Pairing

1. An admin's **Pair** (Settings › Connector) makes a pairing code: `mkp1.` and unpadded
   base64url of `{"a": address, "f": fingerprint, "c": secret}`, as a link code is
   (`link-protocol.md` §4.1). MoneyKata keeps only the SHA-256 of the secret and the code's
   expiry (24 hours); a code works once. Making a code needs the admin's password again
   (S13.7.2).
2. `moneykata-connector pair <code>` calls `hello` at the address and refuses to go on unless
   the key it answers with has the code's fingerprint. It makes the identity and sealing keys
   if it has none, then calls `pair`, signed by the identity key, with `{code, sealingKey,
   version, protocol}`. MoneyKata has no pairing with that key yet, so the signature only
   proves the caller holds the key it sends, and the secret proves it was given the code.
3. MoneyKata records the two public keys, ends any connector paired before (as Unpair does:
   every Connection stopped, every account's sync turned off, S18.4.4), and answers
   `{fingerprint, connectorFingerprint, serverName}`. Both sides show the connector's
   fingerprint for the admin to compare; a mismatch means someone else answered the code
   first, and the admin unpairs.
4. The connector then keeps, per server, the address, the fingerprint and its own keys. One
   connector is paired with one server; `moneykata-connector unpair` forgets it and deletes
   every credential it held for it.

### 4.2 Reports

Every 5 minutes, and at once after an unlock, a run or a change the connector wants to tell
of, `POST /connector/v1/report`:

```json
{
  "locked": false,
  "unlockedAt": "2026-10-15T06:02:00Z",
  "connections": [
    {
      "id": "Conn_01k7…",
      "state": "ok",
      "message": "14 new",
      "lastRunAt": "2026-10-15T05:40:12Z",
      "lastRunAdded": 14,
      "institutionAccounts": [{"name": "Individual", "last4": "4417"},
                              {"name": "Rollover IRA", "last4": "0921"}],
      "signInAddress": null
    }
  ]
}
```

1. `state` is one of `new` (credentials not yet received), `ok`, `needs-sign-in` (the
   institution wants the owner again: Schwab's weekly sign-in, a changed password), `failing`
   (with `message` saying why in the connector's words, never a credential, an amount or an
   account number beyond its last four digits, S18.5). A Connection the connector doesn't know
   (made in MoneyKata, not yet collected) is absent; MoneyKata keeps it as `new`.
2. The answer carries what waits for the connector:

   ```json
   {
     "connections": [
       {"id": "Conn_01k7…", "ownerName": "Alice", "driver": "schwab",
        "label": "Alice's Schwab login", "settings": {…},
        "accounts": [{"id": "Acct_01k7…", "syncAccount": "Individual ••4417",
                      "formats": ["ofx"]}],
        "sealed": {"ciphertext": "…", "sealedAt": "2026-10-15T05:30:00Z"}}
     ],
     "removed": ["Conn_01k6…"]
   }
   ```

   `connections` is every live Connection for this connector with its driver, settings and
   the accounts whose sync names it, each with the formats MoneyKata takes for it; `sealed`
   is present while a credential waits (section 4.3); `removed` names Connections whose
   owners removed them or whose accounts all turned sync off, and the connector deletes their
   credentials and never reports them again.
3. MoneyKata records the report's time, so a connector silent for 15 minutes raises the alert
   of S18.5.2, and shows `locked` as S18.5.1 says.

### 4.3 Credentials

1. **Sealed in the browser** (S18.7.1): the owner's browser fetches the connector's sealing key
   (`GET /ui/api/connector`, with its fingerprint shown), seals the credentials as an X25519
   sealed box (an ephemeral X25519 key, HKDF-SHA256 over the exchange with the label
   `moneykata connector credential` and the Connection's id as salt, AES-256-GCM with a random
   96-bit nonce; the box is the ephemeral public key, the nonce and the ciphertext, base64url)
   and sends the box to `PUT /ui/api/connections/{id}/credential`. MoneyKata stores the box as
   it is and hands it to the connector in the next report's answer.
2. The connector opens the box with its sealing key, files the credentials in its vault under
   the Connection's id, and calls `credential/taken` with `{sealedAt}`; MoneyKata deletes the
   box. A box the connector can't open (sealed to an earlier sealing key) is reported as the
   Connection `failing` with *the credentials were sealed for another connector*, and the owner
   is asked to enter them again.
3. **A sign-in through the institution's page** (OAuth, as Schwab's): the driver calls
   `sign-in` with `{address}`, the institution's sign-in address for this Connection; MoneyKata
   shows it to the owner under Profile › Connections. The owner opens it, signs in, and pastes
   the address they land on into the same credential dialog, which seals it as in 4.3.1; the
   driver reads the code from it and completes the sign-in.
4. **Typed on the connector's host** (S18.7.2): `moneykata-connector connect <connection id>`
   asks for the credentials there and files them in the vault; nothing crosses the wire but the
   next report's state.

### 4.4 Files

`POST /connector/v1/accounts/{id}/files`, multipart with one `file` part and a `meta` part:

```json
{"connectionId": "Conn_01k7…", "format": "ofx", "fetchedAt": "2026-10-15T05:40:10Z",
 "fileName": "schwab-2026-10-15.ofx", "sha256": "…"}
```

1. The account must have its sync set to this Connection, and the Connection must belong to
   the account's owner; otherwise `account-not-synced`.
2. The file goes through the same import as an upload by the owner (S1.3, S18.8): its type is
   checked from its content, imports are idempotent, a PDF is kept without reading or waits in
   the account's inbox, and a CSV uses the account's saved mapping (without one, the post is
   refused with `mapping-missing` and the Connection told so). Activity records it as *by
   MoneyKata Connector, Alice's Schwab login* under the owner.
3. The answer is `{imported: {added, matched, changed}, kept: bool}` as the import dialog would
   show it. `429` with `Retry-After` means the owner's upload limit; the connector keeps the
   file and posts it on a later run.

## 5. Versions

1. The protocol has one number, `1`, in the path (`/connector/v1/`) and in `MK-Conn-Protocol`.
   A server answers the versions it lists as supported and refuses any other with
   `protocol-unsupported`, naming those it speaks, so the admin learns which side needs
   updating. A newer MoneyKata keeps answering the older protocol for at least one release
   after it adds a new one.
2. Within a version, a message may gain fields: a receiver ignores fields it doesn't know, and
   a sender never relies on a new field being understood.
3. Settings › Connector shows the connector's version (from `MK-Conn-Version`).

## 6. Drivers

What each driver posts, and what its `settings` hold (S18.9):

| Driver | Posts | Settings | Credentials |
|---|---|---|---|
| `folder` | each file that appears in a watched folder, to the account whose rule its name matches | the folder's path on the connector's host and the rules (`umb-*.pdf` → an account) | none |
| `ofx-direct` | OFX from the institution's OFX server: transactions and balances | the server's URL, `ORG`, `FID`, the account's type and number | username and password |
| `schwab` | positions, transactions and balances as OFX | the app key | the OAuth sign-in (4.3.3), renewed weekly |

## 7. Refusals

A refusal is JSON `{code, message}` with HTTP 403 (426 for a protocol, 429 for a limit, 404
for an account or Connection that doesn't exist or isn't this connector's), signed as section 3
says when the call carried a nonce.

| Code | When |
|---|---|
| `unsigned` | the signing headers are missing or malformed |
| `clock-skew` | the call's time is more than 60 seconds off |
| `bad-signature` | the signature doesn't match the key, method, path, body, time, nonce and receiver |
| `replayed` | the nonce was seen from that key in the last two minutes |
| `not-paired` | the key isn't the paired connector's, or the pairing has ended |
| `code-used` | the pairing code was used, expired or withdrawn |
| `protocol-unsupported` | the call's protocol isn't one this server answers |
| `account-not-synced` | the account's sync doesn't name this Connection |
| `mapping-missing` | a CSV for an account with no saved mapping |
| `file-refused` | the file's content isn't a type MoneyKata imports |
| `limit` | the owner's upload limit; `Retry-After` says when to try again |
