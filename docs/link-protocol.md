# The link protocol

How two MoneyKata servers talk once their admins have linked them (requirements S11). This
document is the protocol's statement; the code that speaks it is `web/server/src/moneykata/links/`.

## 1. Transport

1. Links are HTTPS POSTs of JSON to the peer's **link address**, the base URL under which
   its `/link/v1/` paths are reached: the public URL by default, or the address set in
   Settings › Linked servers when `/link` is exposed apart from `/ui` (a forwarded port, a
   reverse proxy rule, or an overlay network such as Tailscale).
2. A link address is named by an admin, so the egress guard (S13.5) lets MoneyKata reach it
   even on the LAN. A peer's TLS certificate may be its own (S13.3): what proves who answered
   is the signature on the answer (section 3), checked against the key the link was made with.
3. Everything but `hello` is signed, and every answer to a signed call is signed back.
4. Bodies are JSON, UTF-8, at most 20 MB. A caller waits 10 seconds to connect and 20
   seconds for each read, and refuses an answer that announces more than 20 MB.

## 2. Keys and fingerprints

1. Each server has one **link key**, an Ed25519 key pair made the first time it is needed.
   The private half is a sealed secret (S14.4) and never leaves the server.
2. A key's **fingerprint** is the SHA-256 of its raw 32-byte public key, in hex. Link codes
   carry it whole; screens show its first 16 digits in four groups (`3f9a 21c0 9b7e d4e5`)
   for admins to compare.
3. Keys travel as their raw 32 bytes in unpadded base64url.

## 3. Signed calls

1. A call carries these headers:

   | Header | Value |
   |---|---|
   | `MK-Link-Key` | the caller's public key |
   | `MK-Link-Time` | Unix seconds |
   | `MK-Link-Nonce` | 16 random bytes, base64url |
   | `MK-Link-Signature` | Ed25519 over the lines below, base64url |
   | `MK-Link-Protocol` | the protocol version the call speaks (section 5) |
   | `MK-Link-Version` | the caller's MoneyKata version, for Settings to show |

   The signed text is these lines, joined by `\n`:

   ```
   MK-LINK-1
   <method, upper case>
   <path with its query>
   <SHA-256 of the body, hex>
   <time>
   <nonce>
   <the receiver's fingerprint>
   ```

   Naming the receiver's fingerprint means a call can't be replayed against another server.
2. The receiver refuses, with the codes in section 7: a call without these headers, a time
   more than **60 seconds** from its own clock, a signature that doesn't verify, a nonce it
   has seen from that key in the last two minutes, and a key it has no link with or whose
   link is not in a state that allows the call. Both hosts therefore keep their clocks with
   NTP; a `clock-skew` refusal is named as such on the link's state (S12.11.1.1).
3. **Answers** are signed the same way: `MK-Link-Time` and `MK-Link-Signature` over

   ```
   MK-LINK-1-ANSWER
   <HTTP status>
   <SHA-256 of the body, hex>
   <time>
   <the call's nonce>
   ```

   The caller refuses an answer that isn't signed by the key it expects, so a server
   pretending to be its peer gets nothing past it. Refusals are signed too when the call
   carried a nonce, so a refusal can be told from a forgery.

## 4. Calls

| Path | Signed | Link states | What it does |
|---|---|---|---|
| `GET /link/v1/hello` | no | any | `{protocol, version, fingerprint, key}`, `key` being the link key's public half, whose SHA-256 is the fingerprint: lets a joining server check the fingerprint in a link code before it sends anything |
| `POST /link/v1/ping` | yes | pending, requested, active, paused | `{protocol, version, state}`: the link's state on the answering side |
| `POST /link/v1/join` | yes, by the caller's own key | an invitation | answers a link code (section 4.1) |
| `POST /link/v1/exchange` | yes | active; pending on the joining side | the directories both ways, and the answering side's change for the caller (section 4.3) |
| `POST /link/v1/next` | yes | active | the next part of a large change the caller is pulling (section 4.4) |
| `POST /link/v1/deliver` | yes | active | the caller's change for the answering side (section 4.3) |
| `POST /link/v1/file` | yes | active | `{id}`: one receipt's bytes, as `application/octet-stream`, refused `not-shared` unless a share to that link includes it; the answer's signature takes the bytes' SHA-256 in place of the body's hash, and the caller checks it, and the hash the change carried, before keeping the file |
| `POST /link/v1/end` | yes | requested, pending, active, paused | the link ended on the calling side |

### 4.1 Joining

1. A link code is `mkl1.` and unpadded base64url of `{"a": address, "f": fingerprint, "c":
   secret}`. The inviting side keeps only the SHA-256 of the secret, and the code works once,
   for 24 hours.
2. The joining server calls `hello` at the address and refuses to go on unless the key it
   answers with has the code's fingerprint. It then calls `join`, signed by its own key, with
   `{code, address, household, users}`: the inviting side has no link with that key yet, so
   the signature only proves the caller holds the key it sends, and the secret proves it was
   given the code.
3. The inviting side turns the invitation into a request from that key and answers with its
   own directory; its admin approves or rejects it. The joining side's link waits as
   **pending** until the first `exchange` from the inviting side, which only an approved link
   makes, or until its own `exchange` is answered as active.

### 4.2 Directories

Every `exchange` carries the sender's directory, and its answer the receiver's:

```json
{
  "household": {"serverName": "griffin-parents", "name": "Margaret & Tom", "avatar": {...}},
  "users": [{"id": "User_…", "username": "margaret", "displayName": "Margaret Griffin",
             "email": "margaret@parents.home", "sex": "female"}]
}
```

Only active local users are listed. The receiver keeps each as a remote user by its `id`:
added, updated in place, soft-deleted when it leaves the list and restored when it returns.
It keeps a display name of up to 120 characters and a username of up to 64, and a sex other
than `female` or `male` as `male`; of each item, a kind of up to 20 characters and an owner's
name of up to 120.
Each remote user has a person here, with the name and sex the directory gives (requirements
S10.10.1), used only for gifts.

### 4.3 Exchanges

1. Either side may make an exchange, hourly and when an admin presses **Pull now**; whichever
   can reach the other does, so one reachable side is enough.
2. The caller sends `{…directory, have, wantFull}`: `have` is the sequence number of the last
   change it took from the answering side, and `wantFull` asks for everything (a new or reset
   copy, an overflowed inbox, a change out of sequence).
3. The answer carries `{…directory, state, version, have, wantFull}` for the other direction,
   and `change`, the answering side's change for the caller, when there is one, with `more`,
   how many parts of it are still to come (section 4.4); the caller asks for each with
   `next`, sending its `have`, until `more` is 0.
4. The caller then makes its own change for the answering side, from the `have` and
   `wantFull` in the answer, and sends it with `deliver`, a part at a time, each answered with
   the new `have`.
5. A side whose link is paused refuses with `link-paused`, its message saying until when; the
   caller waits and doesn't count it as a failure, so no one is alerted.

### 4.4 Changes

A change brings the receiver from its `have` to now:

| Field | Meaning |
|---|---|
| `seq` | its number in the sender's sequence for this link |
| `asOf` | when it was worked out |
| `full` | it replaces everything the receiver has from this link |
| `items` | items added or changed: `id`, `kind`, `name`, `ownerName`, `sharedAt`, `viewers` (the receiver's user ids it names), `includeReceipts`, `version` |
| `removed` | ids of items no longer shared |
| `docs` | documents added or changed: `itemId`, `path`, `viewer`, `body` |
| `docsRemoved` | documents gone: `itemId`, `path`, `viewer` |
| `files` | receipts' files added, when their share includes them: their id, item, type, length, hash, thumbnail and what was read from them; the bytes are fetched on their own |
| `filesRemoved` | receipts' files gone (unshared, or pruned at the source, S14.10.6) |
| `progress` | in a large change's parts: `through`, the newest date the parts so far reach; `bytes`, what they hold; `total`, what the whole change holds |
| `signature` | Ed25519 by the sender's link key over the rest as canonical JSON (keys sorted, no spaces) |

1. The sender works each item out as each person it names would see it, with the code its own
   screens use (S11.3.1). An item's documents are its row in its list (`path` empty) and what
   its screens read, by API path: an account's detail, balance series, holdings and latest
   500 transactions; a portfolio's detail, holdings, returns and series; a budget's month and
   trends; a tax book and its panels; a projection; a year's giving; a person's gifts.
2. The sender keeps a hash of each document it last sent, so only what changed travels. A
   receiver whose `have` isn't the sender's last `seq` gets everything.
3. **A large change travels in parts**, oldest to newest (S11.4): past 4 MB of documents and
   files, the first part carries the items and what was removed, and the documents and files
   follow by the newest date each holds, each part signed and numbered as a change of its own
   with its `progress`. The copy fills from its earliest records and is usable up to a date
   while the rest arrives, and the receiver shows how far it has come (*Up to July 2022, 47 MB
   of 2 GB*). A part missed or out of turn makes the next exchange ask for everything. The
   source keeps the parts still to send in memory, so after it restarts `next` answers
   nothing and the caller's next exchange asks for everything.
4. The receiver checks the signature and that `seq` follows its `have` (or that the change is
   `full`); otherwise it asks for everything at its next exchange. It keeps each item's id,
   kind, owner's name, date and the people it names in its main database, never its `name`
   or any figure, which go only into the sealed change, and seals the change whole into the
   link's copy (S11.9.5), where it is applied, its signature checked again, once the copy is
   unlocked. Until the copy's access key is made (S11.9.2.1), a pull keeps only what the main
   database holds and drops the change and its files; making the key asks for everything at
   the next exchange.

## 5. Versions

1. The protocol has one number, `1`, sent in `MK-Link-Protocol` on every call. A server
   answers the versions it lists as supported, and refuses any other with
   `protocol-unsupported`, naming those it speaks, so the admins learn which server needs
   updating. A newer MoneyKata keeps answering the older protocol for at least one release
   after it adds a new one.
2. Within a protocol version, a message may gain fields: a receiver ignores fields it doesn't
   know, and a sender never relies on a new field being understood.
3. Shared items carry their kind (section 6). An item of a kind this server doesn't know is
   kept in the linked copy but not shown, and the window notes that a newer MoneyKata on the
   other side shares something this one can't show yet.
4. Each server shows the peer's MoneyKata version (from `MK-Link-Version`) in Settings ›
   Linked servers.

## 6. Shared items

Each shared item travels as its screens show it, worked out at its source (S11.3.1), in the
changes of section 4.4. Items of a kind the receiver doesn't know are kept in its copy and not
shown (section 5.3).

## 7. Refusals

A refusal is JSON `{code, message}` with HTTP 403 (or 426 for a protocol), signed as section 3
says when the call carried a nonce.

| Code | When |
|---|---|
| `unsigned` | the signing headers are missing or malformed |
| `clock-skew` | the call's time is more than 60 seconds off |
| `bad-signature` | the signature doesn't match the key, method, path, body, time, nonce and receiver |
| `replayed` | the nonce was seen from that key in the last two minutes |
| `not-linked` | the key has no link here |
| `link-<state>` | the link exists here but its state doesn't allow the call |
| `not-shared` | a file no share to that link includes |
| `protocol-unsupported` | the call's protocol isn't one this server answers |
| `code-used` | a link code was used, expired or withdrawn |
| `already-linked` | the two servers already have a link |
| `change-refused` | a delivered change fails its signature check |

A `link-ended` or `not-linked` answer to a signed call ends the link on the calling side, as
`end` would: its copy, the shares to it and its remote users go. A caller refuses an answer
that isn't signed as `answer-unsigned`.
