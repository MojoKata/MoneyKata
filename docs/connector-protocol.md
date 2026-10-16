# The connector protocol

How the MoneyKata Connector talks to the MoneyKata server it is paired with (requirements
S18). This document is the protocol's statement; the code that speaks it is
`web/server/src/moneykata/connector/` on the server's side and `connector/core/` on the
connector's. It follows the link protocol (`link-protocol.md`) wherever the two do the same
thing, so one reading covers both.

**Terms.** The **identity key** (Ed25519) signs the connector's calls and is kept beside its
vault; the **sealing key** (X25519) is what a browser seals a credential to, its public half
held by MoneyKata and its private half kept in the vault; a **sealed box** is such a
credential as MoneyKata stores and hands over, unable to open it; the **vault** is the
connector's encrypted file of credentials and the sealing key, open only while the connector is
**unlocked** with its words; a credential's **bound host** is the one host it may ever be sent
to, fixed when it is filed; the **watched folder** is the one mount the Folder driver reads
inside. Requirements S18 defines them in full.

**The calls at a glance.**

```
 connector                                                  MoneyKata
   |  GET  /connector/v1/hello                                 |  unsigned: {protocol, version, fingerprint}
   |---------------------------------------------------------->|
   |  POST /connector/v1/pair {code, sealingKey}               |  once; signed by the new identity key
   |---------------------------------------------------------->|
   |  POST /connector/v1/report {locked, connections[]}        |  every 5 minutes, signed
   |---------------------------------------------------------->|
   |<----------------------------------------------------------|  {connections: settings, accounts,
   |                                                           |   sealed (only if unlocked)}, removed[]
   |  POST …/connections/{id}/credential/taken                 |  the box is in the vault: delete it
   |---------------------------------------------------------->|
   |  POST …/connections/{id}/sign-in {address}                |  the owner must sign in at the institution
   |---------------------------------------------------------->|
   |  POST …/accounts/{id}/files  (multipart: meta, file)      |  through the owner's import
   |---------------------------------------------------------->|
   |  POST /connector/v1/unpaired                              |  the connector forgot this server
   |---------------------------------------------------------->|
   every answer to a signed call is signed back by MoneyKata's link key
```

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

1. The connector has two keys, made at pairing (S18.4.5): an **identity key** (Ed25519) that
   signs its calls, kept beside its vault so a locked connector can still report, and a
   **sealing key** (X25519) that credentials are sealed to (S18.7.1), whose private half is
   kept **in** the vault, so a copy of the connector's volume opens no box without the words.
   MoneyKata holds only their public halves.
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
2. `moneykata-connector pair <code>`, run with the vault unlocked (it is refused otherwise,
   since the sealing key's private half goes into the vault), calls `hello` at the address
   and refuses to go on unless the key it answers with has the code's fingerprint. It makes a
   new identity key and a new sealing key, then calls `pair`, signed by the identity key, with
   `{code, sealingKey, version, protocol}`. MoneyKata has no pairing with that key yet, so
   the signature only proves the caller holds the key it sends, and the secret proves it was
   given the code.
3. MoneyKata records the two public keys, ends any connector paired before (as Unpair does:
   every Connection stopped, every account's sync turned off, S18.4.4), and answers
   `{fingerprint, connectorFingerprint, serverName}`. Both sides show the connector's
   fingerprint for the admin to compare; a mismatch means someone else answered the code
   first, and the admin unpairs. Until the admin **confirms** the pairing in Settings
   (S18.4.2), the pairing is not trusted: reports are answered, but `sealed` is withheld
   and a file post is refused `not-confirmed`.
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
   is present while a credential waits (section 4.3), **the report said `locked: false`** (a
   locked connector has no sealing key to open it with) **and an admin confirmed the
   pairing** (section 4.1); `removed`
   names Connections whose owners removed them or whose accounts all turned sync off, and the
   connector deletes their credentials and never reports them again.
3. MoneyKata records the report's time, so a connector silent for 15 minutes raises the alert
   of S18.5.2, and shows `locked` as S18.5.1 says. It records the address the report came
   from as well: the first is taken as the connector's; a report from another address is
   still answered but alerts admins until one accepts the new address or unpairs (S18.5.4).

### 4.3 Credentials

1. **Sealed in the browser** (S18.7.1): the owner's browser fetches the connector's sealing key
   (`GET /ui/api/connector`, with its fingerprint shown), seals the credentials as an X25519
   sealed box (an ephemeral X25519 key, HKDF-SHA256 over the exchange with the label
   `moneykata connector credential` and the Connection's id as salt, AES-256-GCM with a random
   96-bit nonce; the box is the ephemeral public key, the nonce and the ciphertext, base64url)
   and sends the box to `PUT /ui/api/connections/{id}/credential`. MoneyKata stores the box as
   it is and hands it to the connector in the next report's answer.
2. The connector opens the box with the sealing key from its vault, files the credentials in
   the vault under the Connection's id **bound to the host the Connection's settings name at
   that moment** (section 6), and calls `credential/taken` with `{sealedAt}`; MoneyKata
   deletes the box. A box the connector can't open (sealed to an earlier sealing key) is
   reported as the Connection `failing` with *the credentials were sealed for another
   connector*, and the owner is asked to enter them again.
3. **The bound host** (S18.7.3): before each run, the connector compares the bound host with
   the host the settings name now. If they differ it sends nothing, deletes the credential, and
   reports the Connection as `needs-sign-in` with *the server address changed from A to B:
   enter the credentials again*; a credential entered then is bound to the new host. No
   change to `settings` can therefore send a stored credential anywhere but where its owner
   entered it for.
4. **A sign-in through the institution's page** (OAuth, as Schwab's): the driver calls
   `sign-in` with `{address}`, the institution's sign-in address for this Connection; MoneyKata
   shows it to the owner under Profile › Connections. The owner opens it, signs in, and pastes
   the address they land on into the same credential dialog, which seals it as in 4.3.1; the
   driver reads the code from it and completes the sign-in.
5. **Typed on the connector's host** (S18.7.2): `moneykata-connector connect <connection id>`
   asks for the credentials there and files them in the vault, bound as in 4.3.3 to the host
   the Connection's settings name, which the connector must have heard of in a report (it
   reports first when it hasn't); nothing crosses the wire but the next report's state.

### 4.4 Files

`POST /connector/v1/accounts/{id}/files`, multipart with one `file` part and a `meta` part:

```json
{"connectionId": "Conn_01k7…", "format": "ofx", "fetchedAt": "2026-10-15T05:40:10Z",
 "fileName": "schwab-2026-10-15.ofx", "sha256": "…"}
```

1. The account must have its sync set to this Connection, and the Connection must belong to
   the account's owner; otherwise `account-not-synced`. Until an admin confirmed the pairing,
   `not-confirmed`: the connector keeps the file for a later run, as for `limit`.
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

| Driver | Posts | Settings | Credentials (sealed, 4.3) |
|---|---|---|---|
| `folder` | each file that appears in the folder named, inside the watched folder, to the account whose rule its name matches | `path`, a folder inside the watched folder, relative to it, empty for the whole of it (an absolute path, `..` or a link out is refused by MoneyKata at the form and by the connector as *failing*); `rules`, one per line: `umb-*.pdf → 3311`, a file-name pattern and the account's last four digits | none |
| `ofx-direct` | the OFX statement the institution's OFX server answers with, as it is | `url`, `org`, `fid`, `accountType` (`CHECKING`, `SAVINGS`, `CREDITCARD`, `INVESTMENT`), `accountId`, and `bankId` (the routing number) for a bank account | `{username, password}`, bound to the host of `url` when filed (4.3.3) |
| `schwab` | positions, transactions and balances from the Trader API, written as an OFX investment statement, one file per account | `appKey` | `{appSecret, landed}`: the app's secret and the address the owner landed on after signing in; the driver keeps the refresh token in the vault, and asks for a new sign-in when it has run out, after seven days. Bound to no host: the driver's is fixed |

A driver's host is the one it declares (`api.schwabapi.com`), or, for OFX Direct Connect,
the server its owner named in the settings **when the credentials were filed**; the egress
allowlist refuses every other, and a changed `url` asks for the credentials again (4.3.3).
The watched folder is set where the connector runs (`MONEYKATA_CONNECTOR_WATCH`, `/watch` by
default, the mount in `compose.yaml`), never by MoneyKata.

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
| `not-confirmed` | an admin has not yet confirmed the pairing (S18.4.2); the file is kept for a later run |
| `code-used` | the pairing code was used, expired or withdrawn |
| `protocol-unsupported` | the call's protocol isn't one this server answers |
| `account-not-synced` | the account's sync doesn't name this Connection |
| `mapping-missing` | a CSV for an account with no saved mapping |
| `file-refused` | the file's content isn't a type MoneyKata imports |
| `limit` | the owner's upload limit; `Retry-After` says when to try again |
