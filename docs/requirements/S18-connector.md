# S18. MoneyKata Connector

The **MoneyKata Connector** keeps accounts current from their institutions without MoneyKata
ever holding, using or seeing an institution's credentials. It is a second service: it keeps
the credentials in a vault of its own, its **drivers** fetch from each institution, and it
pushes what they fetch into MoneyKata's import. MoneyKata can't reach it, read its vault or
ask it for anything.

**Terms used here.**

| Term | What it is |
|---|---|
| **the vault** | one encrypted file in the connector's volume holding every Connection's credentials, the host each is bound to, and the sealing key's private half. It opens only with the words (S18.3). |
| **the words** | 12 BIP-39 words that are the vault's key, kept in the household's password manager and never stored. |
| **locked / unlocked** | whether the words have been given since the connector last started. Locked, it reports and nothing more. |
| **identity key** | an Ed25519 key pair made at pairing, kept **beside** the vault (not in it), whose private half signs every call so MoneyKata knows the paired connector. A locked connector can still report with it (S18.4.5). |
| **sealing key** | an X25519 key pair made at pairing. MoneyKata holds the public half and gives it to browsers; the private half lives **in** the vault and is the only thing that opens a sealed box (S18.4.5). |
| **sealed box** | a credential encrypted in the owner's browser to the sealing key, which MoneyKata stores and hands over but cannot open (S18.7.1). |
| **pairing / pairing code** | the one-time introduction of a connector to a MoneyKata server, from a code Settings shows (S18.4). |
| **Connection** | one sign-in at one institution, owned by a user; its record is in MoneyKata, its credentials in the vault (S18.6). |
| **bound host** | the host a Connection's credentials may be sent to: the one the owner's browser sealed with them, or the admin confirmed on the host, fixed when they are filed in the vault (S18.7.3). |
| **driver** | the part of the connector for one institution, which fetches from it (R2.22). Where nothing can be fetched, the file is uploaded by hand (S1.3). |

**What each side holds, and what crosses.**

```
   owner's browser
        |  seals a credential to the sealing key's public half
        v
 +------------------------------+                              +--------------------------------+
 | MoneyKata                    |   signed report, every 5 min |  MoneyKata Connector            |
 |                              | <--------------------------- |                                 |
 |  holds: identity public key  |   answer: Connections, their |  beside the vault:              |
 |         sealing public key   |   settings and accounts, and |    identity key (signs calls)   |
 |         Connection records   |   sealed boxes, only while   |    the pairing's address + key  |
 |         sealed boxes (can't  |   the connector is unlocked  |  in the vault (needs the words):|
 |         open them)           | ---------------------------> |    sealing key (opens boxes)    |
 |                              |   files for accounts,        |    credentials, each bound to   |
 |  never: a credential, the    |   sign-in addresses,         |    one host                     |
 |  sealing key's private half  |   "credential taken"         +--------------------------------+
 +------------------------------+                                   |
                                                                    |  only to the bound host
                                                                    v
                                                   an institution (Schwab, an OFX server)
```

1. **What it is**: one program, `moneykata-connector`, built from `connector/` in this
   repository into an image of its own, run beside MoneyKata as a second compose service
   (`connector`) or on another machine that can reach MoneyKata's address, such as a laptop.
   1. **A core** (the vault, the schedule, the pairing, the signed calls to MoneyKata and an
      egress allowlist) and **drivers**, one per institution or method, each fetching what
      its institution offers and turning it into files MoneyKata already imports (S18.8).
   2. **Small enough to read.** Python with the standard library, plus the `cryptography`
      wheel for the core alone (its Ed25519 and X25519 keys and the vault's AES-GCM, which
      the standard library doesn't provide) and at most one pinned, hashed dependency per
      driver; no import from MoneyKata. Each driver declares the hosts
      it talks to, the credentials it needs and what it sends, and a test fails when a driver
      reaches another host or grows past 400 lines of code, or the core (the vault, keys,
      signing, the client, the loop, the socket and the command line together) past 1,000:
      lines of code, not counting blank lines, comments and docstrings.
2. **Isolation**: the rules the design rests on.
   1. **Separate**: its own process, unprivileged user (uid 10002), image and volume
      (`connector-data`: the vault and the connector's identity key). MoneyKata never mounts
      that volume; the connector never mounts MoneyKata's data, keys or backups. The volume is
      `/var/lib/moneykata-connector` (mode 0700): `vault.json`, and `pairing.json` (mode 0600:
      MoneyKata's address and fingerprint, the identity key's private half and the sealing
      key's public half). The socket is `/run/moneykata-connector/sock` (mode 0600, on a
      tmpfs). `MONEYKATA_CONNECTOR_DATA` and `MONEYKATA_CONNECTOR_SOCKET` move the volume and
      the socket.
   2. **One way.** The connector only opens connections: to its institutions and to MoneyKata.
      It listens on no network port; its only way in is a Unix socket inside its own container,
      for the commands an admin runs there (S18.3). MoneyKata has nothing to call and no way to
      ask for a credential. A call it makes follows no redirect (a 3xx answer is a failure, so
      nothing is sent again elsewhere), waits at most 60 seconds, and reads at most 25 MB of an
      answer. Its allowlist is kept per driver run, and refuses loopback, link-local and cloud
      metadata addresses, as MoneyKata's egress guard does (S13.5). It verifies every TLS
      certificate: an institution's against the system's roots, MoneyKata's against those roots
      or, for a certificate of MoneyKata's own, against the fingerprint the pairing code
      carried (S18.4.1).
   3. **What each side holds.** MoneyKata holds the connector's public keys and the records
      of S18.6, never a credential. The connector holds the credentials and the sealing
      key's private half, sealed in its vault, and beside the vault an identity key that can
      only sign its calls.
   4. **What a compromise costs**, stated for each thing that can be taken:
      1. **A compromised MoneyKata** gets no credential: the boxes it holds open only in the
         vault. It can serve altered code to a browser and capture credentials typed after the
         compromise (S18.7.1), and it can change a Connection's settings; but a credential is
         bound to the host the owner's browser sealed with it (S18.7.3), so a changed address
         sends nothing and asks the owner again. It cannot reach the connector or ask it for
         anything.
      2. **A compromised connector**, running and unlocked, holds the credentials it was
         given and can post files into the accounts whose owners turned it on (S18.6), which
         their owners would see. From MoneyKata it learns what the report's answer carries:
         each Connection's owner name, label, settings (an OFX server's address and account
         number, a routing number, a Schwab app key) and its accounts' names and last four
         digits; never an amount, a transaction or a password.
      3. **Root on the connector's running host** can read its memory while it is unlocked,
         words and all, and no design changes that.
      4. **A stolen volume, disk or backup of the connector**, or its powered-off machine,
         yields the identity key and the pairing: whoever has it can report as the connector,
         read the answers of S18.2.4.2 and post files, until MoneyKata **unpairs** it
         (S18.4.4), which an admin does at once when a connector's host is lost. MoneyKata
         helps notice it: the address a connector's reports come from is recorded, the first
         one as known, and a report from another address alerts admins until one **accepts**
         the new address (the connector moved) or unpairs (S18.5.4). The vault stays closed
         without the words: no credential, and no sealing key, so no box sealed before or
         after the theft opens. This is why the sealing key lives in the vault.
3. **The vault and its words.**
   1. **Made at install**: `docker compose run --rm connector init` makes a random 128-bit key
      and shows it as **12 BIP-39 words** with the vault's fingerprint, on the terminal and
      never on standard output, so no log keeps them, and won't finish until three of them,
      chosen at random, are typed back. The admin keeps the words in the household's password
      manager. They are never stored; the vault key comes from them. The vault holds every
      Connection's credentials with the host each is bound to (S18.7.3), and the sealing key's
      private half (S18.4.5); a Schwab Connection's entry also holds the app's secret and its
      tokens with when they run out. It is one file, `vault.json`: its format's name, the
      vault's fingerprint, a nonce and the contents, sealed with AES-256-GCM under a key that
      HKDF-SHA256 derives from the words' 128 bits (label `moneykata connector vault key`),
      with the fingerprint as associated data. The words are a random key, not a password, so
      nothing stretches them. Each change seals the whole vault again with a fresh nonce,
      through a temporary file and a rename. The fingerprint, the first 16 hex digits of
      `SHA-256("moneykata connector vault" ‖ key)`, is kept in the clear, to tell another
      vault's words from a damaged file.
   2. **Locked at every start**: the connector starts locked, fetches nothing, and reports that
      it is locked (S18.5); MoneyKata down or locked is a state it reports and retries with a
      growing wait, never a reason to stop. An admin unlocks it with `docker compose exec
      connector moneykata-connector unlock`, which asks for the words without echo and hands
      them to the running connector over its Unix socket; the key stays in memory only. A
      restart, a crash or the host's reboot locks it again. `lock` locks it at once, and
      `status` says what the connector is doing: whether it is locked and paired, its last
      report, and each Connection's state; the image's health check runs `status`.
   3. **Wrong words**: the checksum catches most typing slips at once; a phrase that is a
      valid one but not this vault's is refused by the vault's fingerprint. Five wrong
      attempts in a row make the next wait 15 minutes.
   4. **Lost words**: the vault can't be opened. `moneykata-connector reset` asks for it to be
      confirmed, deletes the vault, makes new words (shown as at `init`, three typed back), and
      unpairs, so the next `pair` makes a new identity key and a new sealing key and every
      Connection's credentials are entered again (S18.7).
4. **Pairing with MoneyKata**, once, as two servers are linked (S11.1).
   1. An admin chooses **Settings › Connector › Pair** in MoneyKata, which shows a one-time
      **pairing code**: MoneyKata's address, its link key's fingerprint, a one-time secret,
      and, when MoneyKata's certificate is its own rather than a public one, the fingerprint of
      the certificate's key, valid 24 hours, in the form of a link code (`mkp1.`,
      `docs/link-protocol.md` §4.1), of which MoneyKata keeps only the secret's hash.
   2. On the connector's host, with the vault unlocked: `docker compose exec connector
      moneykata-connector pair <code>`. The connector makes its **identity key** (Ed25519, for
      signing) and its **sealing key** (X25519, for credentials sent to it, S18.7.1), files the
      sealing key's private half in the vault (so `pair` is refused while the vault is locked),
      introduces itself with the code in one call (`POST /connector/v1/pair`: the code and the
      two public keys, the sealing key signed with the identity key), and both sides show the
      connector's fingerprint for the admin to compare: the connector shows its own, worked out
      from its identity key, never one an answer names. Before anything is sent, the connector
      checks that the key MoneyKata's `hello` gives hashes to the code's fingerprint, and keeps
      that key with the pairing; a failed `pair` leaves any earlier pairing as it was. **The
      pairing is not trusted until an admin confirms it** (Settings › Connector › **Confirm**,
      the password again): a pairing code is a 24-hour bearer secret, and whoever answers it
      first is paired. Until the confirmation, the connector's reports are taken (so its
      fingerprint is known), but it is handed no sealed credential, no file it posts is taken
      (refused `not-confirmed`, and kept for a later run), and no one can seal a sign-in for
      it; the connection dialog says so. Fingerprints that differ mean someone else answered
      the code: Unpair.

      ```
       admin                MoneyKata                        connector host          connector
        | Pair (password again) |                                  |                     |
        |---------------------->| code mkp1.{address, fingerprint, |                     |
        |<----------------------| secret}; keeps SHA-256(secret)   |                     |
        |  carries the code to the connector's host ..............>| unlock (the words)  |
        |                       |                                  |-------------------->| vault open
        |                       |                                  | pair <code>         |
        |                       |                                  |-------------------->|
        |                       |        GET /connector/v1/hello   |                     |
        |                       |<-----------------------------------------------------|
        |                       |  {fingerprint, key} -------------------------------->| SHA-256(key) = code's? else stop
        |                       |                                  |   makes identity key (beside the vault)
        |                       |                                  |   makes sealing key (private half into the vault)
        |                       |   POST /pair {code, sealingKey + its signature}, signed by the identity key
        |                       |<-----------------------------------------------------|
        |                       |  keeps both public keys; answer signed by the link key |
        |                       |------------------------------------------------------>|
        |  both sides show the connector's fingerprint; the admin compares them         |
      ```
   3. **Every call it makes is signed** with its identity key, with a timestamp and a nonce,
      as link calls are (S11.1.3), at `/connector/v1/` on MoneyKata's address, and every
      answer is signed by MoneyKata's link key, so the connector knows it reached the server
      it paired with. The path carries the protocol's version; a call also names it in a
      header, and one MoneyKata doesn't speak is refused naming the versions it does, as
      links are (`docs/link-protocol.md` §5). `docs/connector-protocol.md` states the
      protocol in the link protocol's form. MoneyKata keeps only the public keys. One
      connector is paired with a server at a time: pairing another replaces it, as Unpair
      would (S18.4.4).
   4. **Unpair** (Settings › Connector) ends the paired connector, never a pairing code still
      waiting (which it withdraws as well), refuses its key from then on, stops every
      Connection, and turns every account's sync off. MoneyKata answers the connector's next
      call with a signed `not-paired`, at which the connector deletes the credentials it held
      for that server and its sealing key.
   5. **Where the two keys live, and why.** The identity key sits beside the vault, not in
      it, so a locked connector can still report. It can only prove *I am the paired
      connector*: fetching anything still needs the vault. The sealing key's private half
      lives **in** the vault: a locked connector has no use for it (it can't fetch), and a
      copy of the connector's volume without the words must not open the boxes sealed to it.
      MoneyKata hands a sealed box only to a connector that reports unlocked (S18.5), and
      pairing needs the vault unlocked to file the key.
5. **Status and alerts.** Every 5 minutes, after each run, and every 15 seconds for up to 10
   minutes while a Connection waits for a sign-in (so an address pasted back is exchanged at
   once, S18.7.1), the connector reports, signed: whether it is locked, and each Connection's
   state and last run (*ok, 14 new*; *needs a sign-in*; *failing: the institution refused the
   password*) with the institution accounts it found (name and last four digits, S18.6.1). The
   answer carries what waits for the connector: each live Connection with its settings and
   accounts, sealed credentials to collect, by Connection (S18.7.1), **only when the report
   says the connector is unlocked** (a locked one couldn't open them, S18.4.5) **and the
   pairing is confirmed** (S18.4.2), and Connections removed (S18.6.4), whose credentials it
   then deletes. MoneyKata shows the report and alerts admins (S12.11):
   1. **the connector is locked**: unlock it on its host;
   2. **the connector hasn't been heard from for 15 minutes**: it is stopped, down, or can't
      reach MoneyKata;
   3. **a Connection needs a sign-in or is failing**, to admins and to the owner of each
      account it keeps current;
   4. **the connector reports from a new address** (S18.2.4.4): the alert names the address
      known and the new one, and stays until an admin accepts the new address in Settings ›
      Connector (the password again) or unpairs, whichever address reports after it.

   Reports never carry a credential, an amount or an account number beyond its last four
   digits.
6. **Connections.** A **Connection** is one sign-in at one institution, kept by the
   connector: *Alice's Schwab login*, using the Schwab driver.
   1. **Owned by a user**, the one whose sign-in it is, who names it. MoneyKata holds its
      record (owner, driver, label, state, last run) and, after its first run, **the
      institution accounts the driver found**, by name and last four digits. Its credentials
      exist only in the connector's vault.
   2. **An account's sync**: an account's settings carry **Sync using MoneyKata Connector**,
      offered once a connector is paired. Turning it on asks which Connection (one of the
      owner's, or **New connection…**) and which of its institution accounts this account
      is. Only the account's owner turns it on; an account shared with write can't be.
   3. A Connection can serve several accounts, and a joint account another owner holds
      only once that owner turns its sync on for their own account.
   4. **Profile › Connections** lists a user's own, with their state and accounts, **Sign
      in again**, **Change credentials** and **Remove**; removing one turns its accounts'
      sync off and the connector deletes its credentials. **Settings › Connector** lists
      every Connection's state for admins, never its credentials.
7. **Entering credentials**, chosen per Connection.
   1. **Sealed for the connector** (the usual way): the owner types the credentials in
      MoneyKata, with their password again (S13.7.2) and only once an admin confirmed the
      pairing (S18.4.2), and **the browser encrypts them to the connector's sealing key**
      before anything is sent (an X25519 sealed box, made with the browser's own WebCrypto,
      which current Chrome, Edge, Safari and Firefox provide; a browser without it is offered
      only the stricter way below). The browser first checks the sealing key's signature by the
      identity key the admin confirmed (S18.4.2), and seals, with the credentials, the host the
      dialog shows the owner they go to and the time; the connector refuses a box older than
      the credential it holds. MoneyKata keeps only the ciphertext, which it can't open, until
      the connector collects it on its next report, files it in its vault and confirms which
      box it took (by its time); MoneyKata then deletes that box. A sign-in through the
      institution's own page (OAuth, as Schwab's) works the same way: the connector reports the
      sign-in address, which MoneyKata takes only on the driver's own sign-in host and shows
      with that host; the owner opens it, and pastes back the address they land on, sealed the
      same way, which the connector checks against the random `state` it put in the sign-in
      address. **What this trusts**: the encryption runs in the code MoneyKata serves, so a
      compromised MoneyKata could serve altered code and capture credentials typed after the
      compromise. It can never open credentials sent before.

      ```
       owner's browser              MoneyKata                      connector (unlocked)
        | GET /ui/api/connector        |                                 |
        |----------------------------->| sealing public key, fingerprint |
        | seals {username, password,   |                                 |
        | host, time} in WebCrypto     |                                 |
        | PUT …/connections/{id}/credential {box}                        |
        |----------------------------->| stores the box; cannot open it  |
        |                              |     POST /report {locked: false}|
        |                              |<--------------------------------|
        |                              | answer: settings, accounts, box |
        |                              |-------------------------------->| opens the box with the
        |                              |                                 | sealing key from the vault;
        |                              |                                 | files the credentials, bound
        |                              |                                 | to the host sealed with them
        |                              |   POST …/credential/taken       |
        |                              |<--------------------------------|
        |                              | deletes the box                 |
      ```
   2. **Typed on the connector's host** (the stricter way): MoneyKata shows the command,
      `docker compose exec connector moneykata-connector connect <connection id>`, and an admin
      runs it and types the credentials there. MoneyKata never handles them at all; the admin
      does. The connector files them bound as below, so it must already know the Connection
      from a report; `connect` reports first when it doesn't, and shows the host the
      credentials will go to, and files them only once the admin confirms it.
   3. **Bound to one host.** A credential is sent only to the host it was filed for. When the
      connector files a credential, it records with it the host the owner's browser sealed with
      it, or the admin confirmed at `connect` (an OFX server's address; nothing for a driver
      whose hosts are fixed, like Schwab's), and refuses it when that host is not the one the
      Connection's settings name. Before every run it compares that bound host with what the
      settings name now: if they differ, it sends nothing, drops the credential, and reports
      the Connection as *needs a sign-in: the server address changed from A to B*, so the owner
      enters the credentials again, knowingly, for the new host. A compromised MoneyKata, or
      anyone who can change a Connection's settings, can therefore never redirect a stored
      password to a host of their choosing.

      ```
       connector, before each run of an OFX Connection
        |  bound host (in the vault) == host in settings.url ?
        |     yes -> POST the OFX request to that host, and only there
        |     no  -> send nothing; delete the credential; report needs-sign-in
      ```
8. **What drivers send**: files MoneyKata already imports, posted for one account through the
   same import as an upload (S1.3): OFX or QFX, CSV with the account's saved mapping, or a PDF
   statement. Imports are idempotent, so a repeated post adds nothing. A post counts against
   the upload limit of the Connection's owner (S13.7.5.3); refused for the limit, the connector
   keeps the file and posts it on a later run, so a backlog (a long history fetched at once)
   arrives over a few hours rather than failing. Files waiting, for the limit or for the
   pairing's confirmation, are held in memory: after a restart the drivers fetch again, and the
   import's idempotence drops what arrived before. A file refused for any other reason is
   dropped, and its Connection shows the refusal. A PDF is kept without reading (S1.3.3.6), or,
   where MoneyKata reads that kind, waits in the account's inbox for its owner to check:
   nothing read from a PDF is saved unchecked. Every post is recorded in Activity as *by
   MoneyKata Connector, Alice's Schwab login*.
9. **The first drivers**, for the average cases. A driver pushes what it fetches from its
   institution; an institution with nothing to fetch from, such as UMB, is kept current by
   files its owner downloads and uploads (S1.3), since the downloads land on the owner's
   desktop, not on the server (a watched folder was weighed and turned down, [rejected
   ideas](rejected-ideas.md)).
   1. **OFX Direct Connect**: for institutions that still run an OFX server, fetching
      transactions and balances with the sign-in's username and password, bound to the server
      address the Connection named when they were filed (S18.7.3). Once a day, over `https`
      only, as an OFX 1.0.2 client, it asks for the last 45 days (the Connection's `days`), or
      90 while no account matches the Connection's account number; the server's sign-on codes
      15500 to 15503 mean *needs a sign-in*.
   2. **Schwab**: Schwab's official Trader API, for positions, transactions and balances,
      posted as OFX. Its sign-in lasts seven days, so the Connection asks for a sign-in every
      week (S18.5.3). Once a day it asks for the last 45 days. The app registered at Schwab
      must name `https://127.0.0.1` as its callback, the address the owner lands on and pastes
      back (S18.7.1); an access token is used until a minute before it runs out. The access
      token lasts about 30 minutes and the refresh token about seven days; how long the code in
      the landing address lasts isn't published, so it is exchanged within seconds (S18.5).
      Source: [schwab-py's authentication
      notes](https://schwab-py.readthedocs.io/en/latest/auth.html), kept in
      `docs/external/schwab-py-auth.rst`.
10. **Packaging**: `install/compose.yaml` carries the `connector` service, from the
    `moneykata-connector` image of the same version, `restart: unless-stopped`, read only, all
    capabilities dropped, no published port and its own volume. `docs/operations.md` covers
    installing it, its words, unlocking after a restart, pairing, running it on another machine
    instead, and unpairing a lost one.
