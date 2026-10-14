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
4. Bodies are JSON, UTF-8, at most 1 MB (receipts travel separately, section 6).

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
   link is not in a state that allows the call.
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
| `GET /link/v1/hello` | no | any | `{protocol, version, fingerprint}`: lets a joining server check the fingerprint in a link code before it sends anything |
| `POST /link/v1/ping` | yes | pending, requested, active, paused | `{protocol, version, state}`: the link's state on the answering side |

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

Each shared item travels as its screens show it, worked out at its source (S11.3.1). Their
messages are described with the exchange that carries them.

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
| `protocol-unsupported` | the call's protocol isn't one this server answers |
