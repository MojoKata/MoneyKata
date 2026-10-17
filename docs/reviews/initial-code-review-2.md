# Review 2: the requirements against the code, with secret handling in focus

**Scope.** Every file under `docs/requirements/`, read whole, with `docs/schema.md`,
`docs/link-protocol.md`, `docs/connector-protocol.md`, `docs/operations.md` and `docs/api.md`;
and the code that the requirements describe: the server (`web/server/src/moneykata/`), the
browser app where it seals, unlocks or renders what others send (`web/ui/`), the connector
(`connector/`) and the packaging (`web/install/`). The code was read area by area against
the sections that describe it. Every finding below was checked in the code. Where one was
also run, or rests on a reading not run, it says so.

**Status.** Sections 1 to 10 are the review as written, against the code at `294792b`.
Section 11 records the decisions taken on it. Section 12 says where each finding stands now,
checked against the code rather than the commit messages, and where the next review should
start.

**Paths.** Code paths are relative to `web/server/src/moneykata/`. `mkc/` is
`connector/moneykata_connector/`. Other paths start at the repository's root.

**Ranks** follow `gaps.md`: **High** blocks the first release, **Med** is needed before it,
**Low** can follow it.

**Ids** are this review's own:

| Prefix | What |
|---|---|
| **K** | secret handling: keys, phrases, credentials, tokens, transport |
| **P** | access and privacy between users and households |
| **B** | the code does something other than what the requirements say |
| **N** | the requirements promise it, and nothing builds it or schedules it |
| **A** | requirements written from the code, flagged for review (section 7) |
| **C** | conflicts between sections, or between the requirements and the other docs |

Every item carries a **remedy**, and **alternatives** where there are reasonable ones; where
an item has none, the remedy is the only sensible fix. Review 1 (`initial-code-review-1.md`)
is not re-raised where its fix holds. Two of its
"Done" items do not hold in the code: F8's re-authentication (K7, K14) and candidate gap 14's
new-address email (N12). One holds but is defeated from outside: F7's confirmed pairing (K3).

## 1. Summary

The key hierarchy, the file formats and the signatures are sound and match S15 and the
protocols (section 9). The serious problems are in the plumbing around them:

- **A key route trusts a forgeable address.** In the example setup, any local user on the
  Docker host, or the connector's container, can set the master key to a phrase of their
  own and delete every backup in one request (K1).
- **Transport and content from other servers are trusted too far.** Links and the connector
  never verify TLS. A relay in the path reads everything that crosses, and can pair its own
  keys with MoneyKata in the admin's place (K3). A linked server can run script in this
  app's origin (K2).
- **Failures part-way through a key operation can lock the household out.** The cases are a
  re-encryption, a rotation, or a host command running beside the live server (K5, K6).
  A restore after a re-encryption opens no receipt (K9).
- **Several access paths contradict their own requirements.** Admins can take over any
  account (K8). Access tokens survive a password change (K7). Holders of shares see more than
  was shared (P1–P6).
- **Parts of the requirements were never scheduled.** Categorisation and payee rules (N1), the
  user's data export (N2) and most portfolio charts (N3) are in no milestone. The first
  release is "the seven milestones" (S17.9.8), so they drop out silently.
- **Some figures are wrong.** Average cost, chained wash sales, reinvested dividends, split
  deductions and option trades from broker files are miscounted, and common loan rates can't
  be entered (B1–B6).

| Id | Rank | Finding |
|---|---|---|
| K1 | High | `keys rotate`'s route trusts a forgeable "loopback": a host user or a container sets the master key and deletes the backups |
| K2 | High | A linked server's receipt is served with the type the peer chose and no sandbox: script in this app's origin |
| K3 | High | Links and the connector turn TLS verification off; the connector's pairing can be taken over by a relay |
| K4 | High | The reader worker is no sandbox (pickle back into the server), and hostile files are parsed in the server too |
| K5 | High | A re-encryption or rotation that fails part-way can leave the server unopenable |
| K6 | High | `db backup` and offline `keys rotate` run against the live data directory unguarded |
| K7 | High | Access tokens are made without the password again and outlive a password change |
| K8 | High | Admins can take over any user's account; R1.6 says they cannot see money |
| K9 | Med | After a re-encryption, restoring any earlier copy opens no receipt; the new-host runbook restores none |
| K10 | Med | The recovery phrase is the everyday unlock, and leaks through the TLS key, Docker's logs and keyboards |
| K11 | Med | Rotating the master key alone does not cut the old phrase off |
| K12 | Med | A credential is bound to whatever host MoneyKata names when the connector files it |
| P1 | High | "Last year's tax book" shows a non-consenting filer's figures, through a one-sided spouse |
| P2 | High | A giving plan reads every holder's income, donations and DAF balance |
| P3 | Med | A read share re-shares a receipt by attaching it to the reader's own records |
| P4 | Med | Any user reads the household's whole watched folder |
| N1 | High | Categorisation and payee rules (S2.6, S2.7) are not built and not scheduled |
| B1–B6 | High | Average cost, chained wash sales, reinvestments, split deductions, option trades from broker files, loan rates |

## 2. Secret handling (K)

### K1 (High): the host's key routes trust a forgeable "loopback"

**Requirements.** S15.4.2: `keys unlock` reaches the server "over its own listener on
loopback". S15.7.1.1: `keys rotate`, run in the running server's container, needs "no old
phrase". The code's own reason (`ui/unlock.py:9`): "Only loopback reaches it: host access is
the authentication".

**Code.** `POST /ui/api/keys/rotate` and `GET /ui/api/keys/copies` (`ui/unlock.py:103-164`)
need no session. Their one check is that `request.client.host` is loopback. `ClientAddress`
(`middleware.py:87-108`) has already replaced that address with the right-most
`X-Forwarded-For` hop that is not a trusted proxy. The example `moneykata.toml` trusts
`172.16.0.0/12`. That range covers every Docker bridge: the connector's container, a proxy
container, and the gateway address that connections to the host-loopback port arrive from
(`web/install/compose.yaml:17-18`). The rotate body names the new phrase and, for each copy
on the host, `rewrap`, `delete` or `leave`.

**The failure.** From the connector's container, or as any unprivileged user on the Docker
host, a client sends one request to `127.0.0.1:37373`:

```
POST /ui/api/keys/rotate
X-Forwarded-For: 127.0.0.1
Host: x
Origin: http://x
{"phrase": "<their 12 words>", "copies": {"<each copy>": "delete"}}
```

This deletes every backup, pre-upgrade copy and before-restore folder on the host, and wraps
the keyring under the sender's phrase. From the next restart, the household's phrase opens
nothing. The same forged header defeats the address lockout (S13.7.5.1) and Settings ›
Network.

Without any forging, "loopback" also covers:

- a sidecar sharing the container's network (`tailscale serve`, cloudflared,
  `network_mode: service:`);
- a proxy on loopback left out of `trusted_proxies`;
- every local user in dev mode;
- the reader worker (K4).

S18.2.4.2 says what a compromised connector can do: post files, and learn what the report's
answer carries. Here it can also ransom MoneyKata.

**Remedy.** Host commands reach the running server over a **Unix socket in a 0700 directory
of the server's account** (`/run/moneykata/`), as the connector's do (S18.2.2). The TCP
routes go. Until then, the check must use the socket's own peer address, saved before
`ClientAddress` rewrites it, and the example must trust only the proxy's exact address.
Rewrite S15.4.2 and S15.7.1.1 to say this.

**Alternatives.** A random token written at each start to a 0600 file in the data directory,
which the command reads and sends; or an online rotation that needs an admin session, the
password again and the current phrase, which gives up the lost-phrase escape of S15.5.2.

### K2 (High): a linked server can run script in this app's origin

**Requirements.** S13.7.7: receipt and statement files are served "with
`Content-Disposition`, their checked type, and a `sandbox` CSP, so a PDF can't run script in
the app's origin". S9.4: the type is checked by content.

**Code.** `GET /ui/api/linked/{id}/files/{fid}` streams a linked receipt with
`media_type=row.contentType` (`ui/linked.py:305-335`). That is whatever type the peer's change
named, stored unchecked (`links/changes.py:205`). The route sets no sandbox, no
`Content-Disposition` and no `no-store`. The linked Receipts screen opens the file in a tab
(`web/ui/screens/linked.js:982`).

**The failure.** A hostile or compromised peer shares two "receipts":

- R1, typed `text/html`, holding `<script src="…/files/R2">`;
- R2, typed `text/javascript`.

R2 is same-origin, so `script-src 'self'` allows it. When the viewer opens R1, the script runs
with their session and passes the Origin check. It can read everything the viewer can, or
share all of their accounts with the peer's users. Sharing with a linked server asks for no
password again (K14). The data then leaves through the link itself.

**Remedy.** The local route's rule applies to linked files: accept only S9.1's types,
checked from the bytes when the file arrives, and serve them with `sandbox`,
`Content-Disposition`, `nosniff` and `no-store`. A test walks every file route for these
headers.

**Alternatives.** Serve linked receipts only as downloads (`Content-Disposition:
attachment`), or from a separate origin that carries no session cookie, so a missed type
check still runs nothing in the app.

### K3 (High): links and the connector turn TLS verification off

**Requirements.** `link-protocol.md` §1.2 and `connector-protocol.md` §1.2: a certificate may
be the server's own, and "what proves who answered is the signature on the answer".
Connector §4.1.2: `pair` "refuses to go on unless the key it answers with has the code's
fingerprint". S11.2.1 offers "a forwarded port or a reverse proxy" for linking two LANs, and
S18.1 a connector on a laptop away from home.

**Code.**

1. Every link call is made with `verify=False` (`links/client.py:26, 49, 85`), and so is every
   connector call to MoneyKata (`mkc/client.py:56-58, 98, 114`).
2. The connector checks `hello`'s `fingerprint` field against the code, then takes the
   server's key from a separate `key` field without hashing it (`mkc/core.py:62-68, 78-86`). It
   does so at pairing and again at every start.
3. `pair` prints the fingerprint MoneyKata's answer names, not its own (`mkc/core.py:98`).
4. A link's signed answer covers status, body hash, time and the call's nonce, not who called
   or what was asked (`links/signing.py:105-117`). Refusals are signed for any caller with a
   nonce (`links/routes.py:49-69`), and a `not-linked` answer ends the link here and deletes
   its copy, shares and users (`links/manage.py:331-347`).

**The failure.** A signature proves who wrote an answer; it hides nothing.

- **Reading.** With verification off, anyone who can relay the TLS reads every request and
  answer: an ISP, a hostile network the laptop joins, or DNS or ARP spoofing on a LAN. For a
  link, that is every change, document and receipt, the shared data whole. For the connector,
  it is every statement and export posted, every report and the pairing code.
- **Taking over a pairing.** The relay answers `hello` with the right fingerprint and its own
  key, takes the code from `pair`, and pairs its own keys with MoneyKata. It then tells the
  connector its own fingerprint. Both screens show the same one, so the admin confirms (the
  check review 1's F7 added). Browsers then seal every credential to the relay's sealing key.
- **Ending a link.** The relay takes B's nonce, calls A from a fresh key with it, and hands B
  A's genuine, signed `not-linked`. B deletes every share to that link, its remote users and
  its copy, and A is never told.

**Remedy.**

1. The connector checks SHA-256(`key`) against the code, keeps the key with the pairing, and
   prints its own fingerprint.
2. TLS is verified: against the system's roots where the address has a public certificate
   (the expected `proxy` setup), and against a certificate fingerprint carried in the link or
   pairing code where it doesn't (`tls` mode), with a way to accept a renewed one.
3. A signed answer covers the caller's fingerprint and the request's body hash. Only
   `link-ended` ends a link; `not-linked` marks it broken and alerts admins.
4. Better still for links: the source seals each change and file to the receiving copy's
   public key (S11.9.2.2), which the receiver seals to anyway (S11.9.5.1). Then nothing
   crosses readable, whatever the transport.

**Alternatives.** Verify against public roots only, and say in S11.2.1 that a forwarded port
or a reverse proxy needs a public certificate, while `tls` mode's self-signed pair is for an
overlay network (S11.2.2), which encrypts and authenticates the peers itself.

### K4 (High): the reader worker is no sandbox, and hostile files are parsed in the server

**Requirements.** R1.17: receipts are read "as a sandboxed background job". S9.8.4.2: a
separate worker "so a hostile or broken file cannot take down the server". S1.3.3.2:
statements, including those the connector posts, are read in the same worker.

**Code.**

1. **The worker's boundary.** It is a `multiprocessing` `spawn` child, which is right: it
   inherits no keys (`receipts/reading.py:89-95`). But the server reads each answer with
   `Connection.recv()`, which unpickles it (`:111`). The worker runs as the server's account,
   with the network, the data directory and loopback open to it. Only its priority is lowered
   (`:40-45`), and nothing turns core dumps off.
2. **Parsing in the server.** The server parses as well:
   - thumbnails are made in the upload request with Pillow, libheif and PDFium
     (`receipts/__init__.py:92-118, 177`);
   - every view of a HEIC photo decodes it again (`ui/receipts.py:412-414`);
   - OFX is tokenised in process by ofxtools, whose regex is quadratic on repeated
     `<A><![CDATA[x`. The accounts reviewer measured 104 KB taking 2.5 s; 1 MB takes minutes.
     The parse runs on the request's thread, or synchronously for the connector's files
     (`ui/imports.py:45`, `connector/files.py:77-78`).
3. **Missing limits.** PDF pages are rendered at 300 DPI with no pixel cap
   (`receipts/ocr.py:173-177`), so one large page asks for gigabytes between memory polls.

**The failure.** PDFium, libheif, Pillow, OpenCV and ONNX Runtime are native code with long
records of memory-safety bugs. A file that exploits one reaches the worker through an emailed
invoice or a file in the connector's watched folder. From the worker it can:

- send a pickle that runs code in the server, which holds the data key;
- read the mail folder's and outbox's live links (K15) and the TLS key;
- call K1's route over loopback;
- reach any host, since the egress guard sees only the server's own clients (S13.5).

The parsing in the server needs no exploit to do harm: one crafted OFX file or oversized image
stalls or crashes it.

**Remedy.** Write in S9.8.4 what the sandbox is, and move all parsing of uploaded files into
it, thumbnails and OFX included:

1. Answers are a fixed, length-prefixed JSON shape that the server checks field by field,
   never pickle.
2. Before reading anything, the worker gives up what it doesn't need: Landlock (unprivileged
   on current kernels) denies it the data directory and every network connection; it sets
   `PR_SET_NO_NEW_PRIVS`, closes its descriptors, empties its environment and sets
   `RLIMIT_CORE` to 0.
3. The server marks itself non-dumpable (`PR_SET_DUMPABLE` 0).
4. PDF rendering is capped in pixels, as images are.
5. Say what happens on a kernel without Landlock: refuse to read, or read with a warning in
   Settings › Receipts.

**Alternatives.** Run the reader as its own container or account, with no network and the
data directory closed to it, where Landlock is missing; or turn reading off by default on
such hosts.

### K5 (High): a re-encryption or rotation that fails part-way can leave the server unopenable

**Requirements.** S15.7.2: an interrupted re-encryption "finishes at the next unlock",
"while the server keeps serving". S15.7.1.1: rotation re-wraps the keyring and then each copy.

**Code, each read from it:**

1. **One bad file stops a re-encryption for ever.** `_rewrap_receipts` raises for any `.mkr`
   that opens under neither key, after the database was re-keyed
   (`store/maintenance.py:102-107, 145-163`). Every later unlock runs `_finish_reencrypt` and
   meets the same file. The unlock route doesn't catch `FileError` (`ui/unlock.py:86-98`), so
   the server answers 500 and stays locked until someone deletes the file by hand. A secret
   that doesn't open does the same through `SecretError`. The trigger needs only choices the
   requirements offer: an orphan or damaged file, or a backup restored after a re-encryption
   (K9) and then a re-encryption after a leak (S15.8.2).
2. **The server stops serving.** After `PRAGMA rekey`, `server.store` keeps the old engine
   until every receipt is rewritten (`runtime.py:105`, `store/db.py:43-50`), and each new
   connection fails with the old key. The keys reviewer ran this on the project's sqlcipher3:
   a connection keyed with the old key gets "file is not a database". An exception in the
   copies' step leaves the old store in place until a restart.
3. **A failed rotation reports "refused" after it changed the keyring.** `rotate_running`
   writes the keyring under the new key first (`store/maintenance.py:441`), then applies the
   copies' choices with no per-copy error handling (`store/copies.py:221-255`). The route
   catches only `RefuseStart` (`ui/unlock.py:147-152`), and the command prints that the server
   refused (`keys/cli.py:308-309`). An admin who believes nothing changed destroys the new
   sheet, and after the next restart neither phrase opens the keyring.
4. **Crashes in the copies' step.** A copy's database is re-keyed in place before its keyring
   is rewritten (`store/copies.py:192, 208`). A crash between leaves a copy its own keyring
   can't open. The copies' choices aren't saved, so a "delete" chosen after a leak is dropped
   at the next unlock.
5. **Forget races.** Forget rewrites the keyring outside the maintenance lock
   (`store/copies.py:290-309`), and can put back a stale one.

**Remedy.** Write S15.7 as a journal:

- each step's choices, the copies' included, are recorded in the data directory before they
  are acted on;
- every step is idempotent;
- a file or secret that opens under neither key is set aside and reported, not fatal;
- the new store is installed as soon as the database is re-keyed, and receipts are read under
  either key while the pass runs;
- a rotation's outcome is reported exactly, with the new keyring named, whatever failed after
  it.

**Alternatives.** Until the journal exists, run a dry pass first, opening every receipt and
secret under the current key, and refuse to start when any fails; or take Re-encrypt out of
Settings and make it a host command run with the server stopped.

### K6 (High): host commands run against the live data directory unguarded

**Requirements.** S14.6: no backup "while a re-encryption runs". S15.4.7: `db backup` and
`keys rotate` (when the server is stopped) run "as one-off containers".

**Code.**

- `moneykata db backup` calls the full `open_store` (`store/cli.py:41`,
  `store/maintenance.py:55-83`), with no data-directory lock. It finishes or deletes a pending
  `keyring.next` (`:61-62, 181-186`), and migrates the live database, or at head syncs its
  views (`store/migrate.py:68-104`).
- Offline `keys rotate` takes no lock either. It decides the server isn't running whenever
  `GET /ui/api/unlock` doesn't answer 200 (`keys/cli.py:162-170`), which Settings › Network's
  app ranges turn into a 404 for loopback.

**The failure.**

1. **During a re-key.** A `db backup` started as the server re-keys sees a database that
   doesn't open with `keyring.next`, and deletes it. The server's `os.replace` then fails, and
   the database and the receipts already rewritten are under a key that exists nowhere.
2. **Later in a re-encryption.** Both processes rewrite the same receipt through the same
   temporary name (`keys/files.py:100-110`), and it ends interleaved.
3. **Before an upgrade.** "Back up first" run with the new image migrates the live database
   under the old, running server.
4. **A lost phrase.** The escape from a lost phrase (S15.5.2) asks for the current phrase.
   Given it, the offline rotation rewrites the keyring under a running server whose keyring in
   memory is now stale (K5.3).

**Remedy.**

- `db backup` asks the running server, over K1's socket, to make the backup; when the server
  is stopped, it takes the data-directory lock and opens the database read only, with no
  migration.
- Offline `keys rotate` takes the lock and refuses while the server holds it.
- A `keyring.next` is never deleted, only set aside with a log line.

**Alternatives.** Refuse `db backup` and offline `keys rotate` while the server holds the
data-directory lock, pointing to Settings › Backups › **Back up now** and to the online
rotation.

### K7 (High): access tokens skip re-authentication and outlive a password change

**Requirements.** S13.7.2: making an access token needs the password again. S10.9.4: a token
stops when revoked, expired, or its user made inactive. S13.7.1: a password change ends every
session.

**Code.** `POST /profile/tokens` has no `recent_auth` (`ui/tokens.py:89-112`). `tokens.find`
checks revoked, expired and inactive only (`tokens.py:45-58`). A password change or reset ends
sessions only, while its email says "every session was signed out" (`auth/users.py:460-485`).
Making a token sends no email.

**The failure.** Someone with a minute at an unlocked browser makes a year-long token that
reads everything. The owner's password change, or a reset after they notice, leaves it
working.

**Remedy.** Re-authenticate, as S13.7.2 says. A password change or reset revokes the user's
tokens, or the email names those still live. Making a token is emailed, as the other
account-security changes are (S10.1.9). Review 1's F8 is marked Done, but this route, and
those in K14, still skip it.

### K8 (High): admins can take over any user's account, and R1.6 says they cannot see money

**Requirements.** R1.6, S10.2: "Admins are not superusers of money." S16.2: an admin opens a
written email "so an invitation or reset link can be passed on". S10.1.6.4: an admin's reset
of two-step.

**Code.**

- A reset request needs no sign-in (`ui/session.py:363-370`), and with no SMTP host its email
  goes to the mail folder (`mail.py:218-222`).
- Opening a written email needs the admin's own password and records nothing
  (`ui/settings.py:185-196`).
- The admin's two-step reset (`ui/users.py:184-203`) emails the user, into the same folder.
- `smtpHost` and `publicUrl` change with no re-authentication (`ui/settings.py:51-69`).
- The Activity entry for the reset reads "Bob reset their password", with Bob as the actor
  (`auth/users.py:447, 464-472`).

**The failure.** The paths in:

1. **With no SMTP** (the first milestone's mode), an admin asks for Bob's reset, resets his
   two-step, opens the email and sets his password. Bob's notices land in the folder only
   admins read.
2. **With SMTP set**, the admin points `smtpHost` at their own server, or changes `publicUrl`,
   so that genuine reset emails carry `https://attacker/ui/reset#…`.

Separately, the admin holds the phrase and the host, so `db shell` reads everything.

**Remedy.**

1. Say in S10.2 what admins are trusted with (the phrase, the host, Settings) and what the app
   keeps from them.
2. **Open** shows only invitations, and emails to the admin themselves.
3. Opening an email, an admin's two-step reset, and a change of SMTP host or public URL are
   recorded in Activity with the user as owner, and shown to the user in the app at their next
   sign-in.
4. Changes of `smtpHost` and `publicUrl` need the password again.

**Alternatives.** Accept that admins are trusted, and say so plainly in R1.6 and S10.2,
keeping only the Activity trail and the in-app notices; or have a second admin approve a
reset of another user's two-step.

### K9 (Med): restoring after a re-encryption opens no receipt, and the runbook restores none

**Requirements.** S14.6: receipt files "are written once and never changed", so they stay out
of backups. S9.2: "a re-encryption (S15.7.2) writes each one again under the new key".
S15.7.2: a verified backup is made first, and a copy may be "left" with its old data key.
S15.5.1: after a lost host, "restore the backup … Nothing is lost". `operations.md` §6.2 copies
in a backup folder and restores.

**Code.**

- A receipt file's header names no key (`keys/files.py:4-27`).
- `db restore` puts back the database and its keyring, leaves `receipts/` where it is, and
  checks nothing about it (`store/maintenance.py:23-27, 352-385`).
- It leaves a pending `keyring.next` behind, which the next unlock deletes (`:181-186`).
- It accepts any phrase that opens the backup, so it can bring back a phrase that was rotated
  out after a leak (`:336-361`), and says nothing.
- It leaves the `Link` rows as the backup had them (`copyPublicKey`, `copyFolder`, `gotSeq`).
  As a result, *Create the access key* is refused `key-exists` (`links/copies.py:35-38`), and
  no full pull is asked for.

**The failure.**

1. After a re-encryption, restoring any earlier copy restores a keyring whose receipts key opens
   none of the files on disk: the "known-good" backup, a copy left, a `pre-upgrade/` copy. The
   unlock then reports thousands of unopenable files. The keyring that would open them sits in
   `before-restore-*/`, which Settings offers to Remove.
2. On a new host, following §6.2 restores no receipt at all, since none is in a backup.
3. A restored copy can revive the phrase a leak retired.
4. The links stay empty.

**Remedy.**

1. Each file's header names its key id, and the keyring keeps each data key still in use.
   Alternatively, `db restore` checks a receipt against the backup's key and, when it fails,
   re-wraps the receipts from the replaced keyring.
2. §6.2 and S15.5.1 restore `receipts/` from the host's backup of the same moment.
3. A restore names the phrase it restores under, and asks before reviving a previous one.
4. A restore resets each link's copy state.
5. Correct S14.6's "never changed".

### K10 (Med): the recovery phrase is the everyday unlock, and it leaks on the way

**Requirements.** S15.4.1–2: every start waits for the 12 words, on the locked screen "from any
browser, which is what makes a phone enough after a power cut", or on the host. S15.6.2: at
least one copy offline. S15.8.1: a leaked phrase is a leaked copy of everything, for ever.
S15.1.7: the `tls/` pair "protects the listener, not the data". S15.4.6: the phrase is "never in
a file".

**The problem.** The one secret that, with any copy, opens everything for ever is the one typed
after every power cut, update and crash, on whatever device is at hand. In practice the
password-manager entry becomes the working copy. Each typing can leak it:

1. **The `tls` key.** In `tls` mode the phrase crosses under the self-signed key in `tls/`,
   which is plain in every snapshot (`listener.py:58-66`). Whoever holds a snapshot (the thief
   S15.3.7 calls harmless) can serve the certificate the household's browsers already
   accepted, capture the phrase at the next unlock, and open their snapshot.
2. **Docker's logs.** `keys init` and `keys rotate` print the sheet to standard output and echo
   the three words back (`keys/cli.py:23-24, 65, 89, 104, 255`). `docker compose run` keeps
   standard output in its json-file log (`compose.yaml:29-31`), so the words sit in
   `/var/lib/docker/containers/<id>/` while the container exists, and in any snapshot or log
   shipper. The connector's `init` does the same with its words.
3. **The browser.** The locked screen's field (`web/ui/screens/locked.js:30-33`) masks with
   `-webkit-text-security`, which Firefox lacks, and doesn't turn `autocorrect` or
   `autocapitalize` off, so phone keyboards learn the words.

**Remedy.**

1. Prefer an **unlock passphrase** beside the phrase. The keyring holds the data key wrapped
   twice: under the phrase's key, and under a key stretched from an admin's passphrase
   (argon2id). The passphrase unlocks after a restart; the phrase stays offline, for recovery
   and rotation. The cost is an offline guessing target as strong as the passphrase.
2. Whatever is chosen:
   - write the sheet and read the words on `/dev/tty`, refusing to run without a terminal;
   - give the field `autocorrect="off"`, `autocapitalize="none"` and a mask that works in
     every browser;
   - say in S15.1.7 that in `tls` mode the pair protects the phrase in transit, so `tls` mode
     is for testing, as S13.3 says.

### K11 (Med): rotating the master key alone does not cut the old phrase off

**Requirements.**

- S15.7.1: rotation re-wraps the data key "and nothing else".
- S15.7.3's timeline: after a rotation, "B4, B5 wrapped under the new key; B1–B3 still open
  with the old phrase".
- S15.8.2.3: rotate "so the leaked phrase opens nothing made from now on".
- S15.8.4: "rotate on a calm schedule: once a year is plenty".

**The problem.** The data key is the same before and after a rotation. Whoever holds the old
phrase and any one copy from before the rotation gets the data key from that copy. The copy
can be B1, or a host snapshot, which S15.6.7 tells admins to keep and send off site. That key
opens B4, B5 and the live database directly, keyring or not. S15.8.2 has the steps in the right
order (re-encrypt before rotating), but other text presents rotation alone as cutting the old
phrase off:

- the timeline;
- S15.8.2.3;
- S15.8.4's yearly rotation;
- Forget (S15.7.1.4).

**Remedy.** Either make every rotation re-encrypt, which makes the timeline true at the cost of
rewriting the receipts. Or say in S15.7.1, S15.7.3 and S15.8.4 that rotation alone changes only
which phrase unwraps the keyring. Until a re-encryption, an old phrase plus any old copy still
opens every later copy, and the yearly reminder is for both.

### K12 (Med): a credential is bound to whatever host MoneyKata names when it is filed

**Requirements.** S18.7.3: no one who can change a Connection's settings "can … ever redirect
a stored password to a host of their choosing". S18.7.1: a compromised MoneyKata "can never
open credentials sent before".

**Code.**

- The browser seals the credentials alone, with the Connection's id as the HKDF salt
  (`web/ui/app/sealed.js:5-7`).
- The connector binds a box to the host named in MoneyKata's latest answer (`mkc/core.py:217-243`).
- `connect` on the host does the same, and never shows the admin the host
  (`mkc/core.py:142-157`, `mkc/main.py:136-143`).
- Changing a Connection's settings needs no password again (`ui/connections.py:208-244`).

**The failure.** A box waits in MoneyKata until the connector reports unlocked and confirmed:
minutes, or hours after a restart. Whoever changes the Connection's `url` in that window has
the password filed bound to their host. That is a session thief, or MoneyKata compromised after
the owner sealed. The "stricter way" binds to an address the admin never sees.

**Remedy.**

- The browser seals `{credentials, host}`, with the host the dialog showed the owner.
- The connector binds to the host inside the box, and refuses one that differs from the
  settings.
- `connect` prints the host and asks for it to be confirmed.
- Changing an OFX server address joins S13.7.2's list.

**Alternatives.** Set an OFX server's address on the connector's host, as the watched folder
is (S18.9.1), so that no setting from MoneyKata names a host at all.

### K13 to K25 (Med and Low): the rest

13. **K13 (Med): a changed host receives the stored secret.**
    - `smtpHost` and `bitcoinNodeHost` change without re-authentication, and the stored
      password goes to the new host (`mail.py:114-115`, `bitcoin/sync.py:30`).
    - Changing `smtpHost` and pressing **Send a test email** delivers the SMTP password to
      whoever runs that host. That sidesteps the re-authentication S13.7.2 puts on the secret.
    - **Remedy:** clear a secret when the host it belongs to changes, so it is entered again
      for the new host. **Alternative:** ask for the password again for a host change, and
      bind each secret to its host as the connector binds credentials (S18.7.3).
14. **K14 (Med): re-authentication is still missing on several routes.** Review 1's F8 is
    marked Done, but these skip the password again, against S13.7.2:
    - making a user an admin through `PATCH /users/{id}`, `POST /users` and approving a sign-up
      (`ui/users.py:130-147, 165-166, 234-242`; only `PATCH /groups` asks);
    - sharing with a linked server, and Include receipts (`ui/sharing.py:209-241`);
    - a price source's key (`ui/prices.py:216-245`).

    S13.7.2 should also list what redirects a secret or a link: a Connection's settings
    (K12), and the SMTP host and public URL (K8, K13).
    - **Remedy:** `recent_auth` on each route, and the three additions written into S13.7.2.
      **Alternative:** a test that walks every route, as S13.8.6's version test does, and
      fails when a route that changes something in S13.7.2's list skips it, so a new route
      can't miss it either.
15. **K15 (Med): the outbox holds emails in the clear, for ever.**
    - With SMTP set, every email is written to `outbox/` in the data directory first, in the
      clear, and is removed only when sent (`mail.py:209-233`). One refused outright becomes
      `.refused` and is kept for ever (`:262-266`). Only the mail folder expires (`:185-198`).
    - An outage leaves every link of the day in the data directory and its snapshots, and alert
      emails name accounts (`alerts.py:364`).
    - S15.1.7 didn't list the outbox; A12 writes it into S15.1.7 and S16.2 as built.
    - **Remedy:** queue emails in the database, which is encrypted, and remove each when sent
      or when its link expires; a refused one keeps only its recipient, subject and error.
      **Alternative:** keep the files, sealed under a key derived from the data key, and
      expire them with their links.
16. **K16 (Med): two-step codes can be brute-forced.**
    - The pending token survives wrong codes and isn't tied to an address
      (`auth/twostep.py:254-273`), with no cap per token or per user.
    - The slowdown sleeps after the failure is counted, so parallel requests aren't slowed
      (`ui/session.py:231-233`). The lockout is per exact IPv6 address (`ratelimit.py:103-119`).
    - With the password and a /64, a guess succeeds in about half a day.
    - **Remedy:** void the pending token after five wrong codes, so the password is needed
      again; count IPv6 addresses by their /64; take one attempt per token at a time.
      **Alternative:** lock the user's two-step for 15 minutes after ten wrong codes from
      anywhere, accepting that someone with the password can then keep its owner out.
17. **K17 (Med): password oracles and timing outside the lockout.**
    - `POST /reactivation-requests` answers `account-active` for any active user's right
      password, outside `SignInGuard` (`ui/session.py:458-464`).
    - Re-authentication and the current-password check share only a 30-request window.
    - Sign-up runs argon2 only for a new address (`auth/signup.py:94-103`), so its timing tells
      whether an email has an account, against S10.1.4.1.
    - **Remedy:** put reactivation, re-authentication and the current-password check behind
      the sign-in guard, counted as sign-ins; answer a reactivation request the same whatever
      the account's state; hash the sign-up password before looking the address up, so both
      paths take the same time. **Alternative** for sign-up: answer at once and do the work in
      the background, as the email is sent anyway.
18. **K18 (Med): the link guard's holes.**
    - A joining server's address is stored unchecked (`links/manage.py:184`). Link hosts,
      requested ones included, count as allowed by name, which skips the loopback, link-local
      and metadata refusal (`links/peers.py:15`, `ui/prices.py:154`, `net.py:77-78`).
    - URLs are joined by concatenation (`links/client.py:19-20`). A code holder's
      `http://127.0.0.1:2019/stop?` gets signed POSTs on Approve, Reject and every exchange.
    - `Guard.check` resolves a name and httpx resolves it again, so DNS rebinding passes
      (`net.py:79-104`).
    - Chunked answers escape the 20 MB ceiling (`net.py:105-109`, `links/client.py:85-93`).
    - `http://` link addresses are accepted, against S11.2 (`settings.py:72`).
    - **Remedy:** refuse, at the form and in `join`, a link address that isn't `https`, has a
      query or fragment, or resolves to loopback, link-local or metadata; never exempt a
      peer-supplied host from the address refusal, and allow it only once its link is
      active; build URLs from the parsed base and a path; connect to the address the guard
      vetted, keeping the name for SNI and `Host`; read every answer through the ceiling.
      **Alternative** to connecting by address: a resolver inside the guarded transport, so
      httpx and the SMTP and Electrum clients resolve only through it.
19. **K19 (Med): the logs can hold amounts and payees.**
    - The engine doesn't set `hide_parameters` (`store/db.py:47-56`), so `log.exception`
      (`errors.py:279`, `tasks.py:208`, `alerts.py:541`) writes SQL parameters.
    - Error ids reach the log only for unhandled exceptions (`errors.py:248-253`,
      `middleware.py:39-52`), against S13.7.8.
    - A receipt read error puts a host path in `detail` (`ui/receipts.py:418`).
    - A peer's refusal message is copied verbatim into alerts and emails
      (`links/manage.py:340-343`).
    - **Remedy:** `hide_parameters=True` on every engine, and a test that a failing insert's
      log line holds no parameter; every problem logged with its id, status and code; a fixed
      `detail` for file errors, with the path in the log; a peer's refusal shown by its code
      with this server's own words, its message kept in the log only.
20. **K20 (Med): the connector's lost-host response can fail.**
    - Unpair acts on the newest row, which while a code is out is the pending one
      (`connector/manage.py:53-59, 206-213`). After Pair, then Unpair, the stolen connector stays
      paired.
    - The new-address alert clears whenever the genuine connector reported last
      (`alerts.py:234`, `connector/manage.py:258-271`), against S18.5.4.
    - A MoneyKata-side Unpair never makes the connector delete its credentials
      (`mkc/core.py:163-171`), against S18.4.4.
    - `reset` makes a vault with no sealing key, so every later box fails (`mkc/vault.py:54-68`).
    - **Remedy:** Unpair ends the paired row and withdraws any code out; an address not yet
      accepted is kept apart from the last one, and its alert stays open until an admin
      accepts it or unpairs; a signed `not-paired` makes the connector delete its credentials
      and its sealing key; `reset` makes a new sealing key and asks for a pairing again.
      **Alternative** for `reset`: it unpairs, so the next `pair` makes both keys afresh.
21. **K21 (Med): the Folder driver follows links.** Each file is read through any symbolic link
    (`mkc/drivers/folder.py:76-91`). A link named `umb-1.csv` pointing at
    `/var/lib/moneykata-connector/pairing.json` posts the connector's identity key to MoneyKata,
    which S18.2.4.1 says no setting can do. (Who can read the folder is P4.)
    - **Remedy:** open each file with `O_NOFOLLOW`, take only regular files whose resolved
      path is inside the root, and say so in S18.9.1. **Alternative:** mount the watched
      folder into a separate, read-only path namespace, with the connector's volume out of
      the driver's reach (a second container for the Folder driver).
22. **K22 (Low-Med): unauthenticated `/link` takes the write lock.** Every request, `hello`
    included, opens a write transaction and decrypts the link key before any check
    (`links/routes.py:15-24, 40, 77`). Bodies up to 20 MB are read before the signature, and
    there is no rate limit (N9). A flood stalls every write in the app.
    - **Remedy:** look the caller's key up in a read transaction and check the signature
      before any write; decrypt the link key only to sign an answer; refuse an unknown key
      after reading its headers, before its body; rate-limit unsigned calls by address.
      **Alternative** for `hello`: answer it from the fingerprint held since the unlock.
23. **K23 (Low-Med): settings, copies and keys outside the lock.**
    - Settings › Network's ranges are in the encrypted database, so while locked the locked
      screen and the unlock answer every address (`app.py:107-116`). A14 writes this into
      S16.14. **Remedy:** keep a copy of the app's ranges outside the database (in
      `moneykata.toml`, or a plain file the server writes), which a locked server applies.
      **Alternative:** keep the behaviour and tell admins, in Settings › Network, that the
      proxy is what limits the locked screen.
    - Removing a copy needs only the password (`ui/settings.py:710-724`), so a stolen admin
      password deletes every backup one call at a time. **Remedy:** Remove asks for the
      phrase, as Re-encrypt's "delete" does. **Alternative:** the newest verified backup can't
      be removed from the browser at all.
    - S11.9.10 says a locked copy is safe from "this server's admin … unless they also have the
      words", but S11.9.2.1 has that admin make the words. **Remedy:** the first person the
      shares name makes the access key, in the linked window, so the admin need never hold it.
      **Alternative:** drop "this server's admin" from S11.9.10.
24. **K24 (Low-Med): the connector's smaller trust points.**
    - The sealing key isn't tied to the identity key the admin confirmed: the dialog shows the
      identity key's fingerprint (`ui/connections.py:83`) while sealing to a database value.
      **Remedy:** the connector signs its sealing key with its identity key at pairing, and
      the browser checks the signature before sealing.
    - Sign-in addresses are any `https` URL the connector sends (`connector/routes.py:157`),
      shown as "Open Schwab's sign-in": phishing for the institution's password. **Remedy:**
      accept only the driver's declared OAuth host and path, and show the host in the
      dialog.
    - Boxes carry no time, so an older box can be handed over again. **Remedy:** seal a time
      into each box, and have the connector refuse a box older than the credential it holds.
    - `credential/taken` deletes whatever box waits, a newer one included
      (`connector/manage.py:355-368`). **Remedy:** the call names the box's `sealedAt`, as
      `connector-protocol.md` §4.3.2 says, and only that box is deleted.
    - The connector's allowlist refuses no loopback or metadata address, and reads answers
      without a limit (`mkc/client.py:68`). **Remedy:** the server's guard rules (S13.5) in the
      connector, and a ceiling on each answer.
    - Schwab's OAuth has no `state` (`mkc/drivers/schwab.py:205`). **Remedy:** a random
      `state` in the sign-in address, checked in the address pasted back.
25. **K25 (Low): leftovers, each with its remedy.**
    - A linked copy's database key lingers in the engine's connection factory after a release
      (`links/copy.py:151`, `store/db.py:49`). **Remedy:** the factory reads the key from a
      `bytearray` that the release overwrites, and refuses to connect after it.
    - Uploads over 1 MB are spooled to temporary files in the clear, which is tmpfs in the
      compose file but disk elsewhere. **Remedy:** spool in memory up to the upload limit.
      **Alternative:** refuse to start when the temporary directory is not a tmpfs.
    - A link's inbox file names the local counter, not the source's `seq`, so an old full
      snapshot put back while the copy is locked re-applies, bringing back revoked items
      (`links/changes.py:69-75, 128-135`). **Remedy:** the source's `seq` in each inbox file's
      associated data, and an apply that refuses a `seq` at or below the last applied.
    - A backup renamed to a newer one's name passes `verify-backup`, which shows only the name
      (`store/cli.py:57`). **Remedy:** `verify-backup` and `restore` show the manifest's
      `made`, and refuse a folder whose name disagrees with it.
    - The live stream's `alert` event carries titles that name accounts and people
      (`alerts.py:578`), against S12.6. **Remedy:** the event carries the count only, and the
      screen reads the alert through the API.
    - Dev mode ships in the image, and runs with `--data /tmp/x` and the seed users' fixed
      password (`main.py:52-57`). **Remedy:** leave `dev/` out of the image. **Alternative:**
      `moneykata dev` refuses to run outside a checkout.

## 3. Access and privacy (P)

1. **P1 (High): last year's tax book leaks a non-consenting filer.** `books.previous()` takes
   any book of last year that shares a filer, accepted or not (`taxes/books.py:303-313`).
   `create_book` copies that book's added accounts (`ui/taxes.py:149-155`), and `counted()`
   counts them with no access check (`taxes/books.py:127-128`). A spouse relationship is
   one-sided (`people/__init__.py:319-322`).
   - **The failure:** Mallory declares Bob her spouse and makes a joint book naming him. She
     sees his last-year AGI, tax, refund and carryovers, his documents, and the 8949 rows of
     the accounts he had added.
   - The declared marriage also reruns Bob's wash sales against her trades (S3.8,
     `ui/people.py:342`).
   - **Remedy:** read last year's book only when every filer of the new book has accepted it,
     count an added account only for those who can see it, and make a spouse need both
     people's confirmation (C42). **Alternative:** show last year's figures only to the
     filers of last year's book, whoever opens this year's.
2. **P2 (High): a giving plan reads every holder's money.** `givers()` returns every holder,
   read shares included (`giving/__init__.py:60-65`), and `donations()`, `income()` and
   `funds()` read all of their accounts (`:132-138, 174-192, 228-231`).
   - **The failure:** Alice shares her plan with Bob to read, and she now sees Bob's take-home
     pay, his donations and his DAF balance.
   - **Remedy:** count only the owner's accounts, and say so in S7.9.1. **Alternative:** a
     holder's giving counts once they tick *Count my giving in this plan*, as *Count in my
     totals* works for accounts (S10.7), and only then.
3. **P3 (Med): a read share re-shares a receipt.** Attaching needs only read on the receipt
   (`ui/receipts.py:350-357`, `ui/gifts.py:687`, `ui/giving.py:683`, `ui/taxes.py:877-878`,
   `ui/education.py:472`); `receipts.attach` checks write on the target only
   (`receipts/__init__.py:315-320`).
   - **The failure:** Bob attaches Alice's receipt to his own transaction and shares that
     account on, to Carol or to a linked server. Alice can neither detach it nor delete it,
     against S10.3.1 and R3.4.
   - **Remedy:** attaching needs write on the receipt: its owner, or a write share on what it
     is attached to, as S10.3.1 says. **Alternative:** a link to someone else's receipt is
     seen only by those who can read the receipt itself, so attaching shares nothing.
4. **P4 (Med): any user reads the household's watched folder.** Any user can make a Folder
   Connection with an empty path and the rule `*` to an account of their own
   (`ui/connections.py:160-205`). The record of what was posted is shared across Connections
   (`mkc/drivers/folder.py:88-92`).
   - **The failure:** Bob receives Alice's statements from her mounted Downloads, and whichever
     Connection runs first claims each file.
   - **Remedy:** S18.9.1 gives each sub-folder of the watched folder to one user, an admin
     assigning it, and a Folder Connection may name only its owner's; the posted record is
     kept per Connection. **Alternative:** only admins make Folder Connections, choosing the
     account each rule posts to.
5. **P5 (Med): a linked server writes into this household before approval.** `answer_join`
   applies the joining server's user list before the admin decides, and answers with this
   server's full list, emails included (`links/manage.py:181-189`).
   - Each remote user takes over the one local person of the same name who isn't a user, and
     sets it public (`people.for_new_user`, `people/__init__.py:42-52`). Every later exchange
     renames it (`links/manage.py:227`).
   - A rejected request leaves these people behind.
   - A local user can do the same: whoever creates a person "Bob Smith" before Bob is invited
     stays its owner, and can later change his birthday or set `diedOn`.
   - **Remedy:** nothing crosses before approval (the lists go in the first exchange); a
     remote user gets a person of its own, joined to an existing one only when a local user
     who can change that person confirms it, never changing `private`; a person who becomes
     a user is changed only by that user and admins from then on. **Alternative** for remote
     users: they get no person at all until someone adds a gift for them.
6. **P6 (Med): data crosses a link beyond the share.**
   - Budget recurring payments carry the `accountId` and `accountName` of every account behind
     the budget (`ui/budgets.py:405-425`).
   - A gift's `paid.accountName` and its receipt documents cross without Include receipts
     (`ui/gifts.py:472-498`).
   - **Remedy:** the source drops an account's id and name from what it sends unless that
     account is shared with the same people, writing *an account not shared*, and sends a
     gift's documents only with Include receipts. **Alternative:** S11.3.1 says that account
     names cross with the figures they explain, and ids never do.
7. **P7 (Med): smaller leaks between users, each with its remedy.**
   - A tax-book helper with write can add accounts (`ui/taxes.py:542`), against S8.14.2.
     **Remedy:** adding an account needs a filer, not write.
   - A tax book can be shared with a linked server (`sharing.py:114-131`), against S8.14.3,
     and only its creator can change its sharing, though every accepted filer owns it.
     **Remedy:** refuse the kind in `sharing.save` (or drop the exception, C34), and let any
     filer change the sharing.
   - A shared projection shows the owner's account values and daily tracking
     (`projections/__init__.py:177, 439`), which S5.1.1 hides in the same portfolio.
     **Remedy:** a viewer sees the projection's results without the values of accounts not
     shared with them. **Alternative:** say in S6 that sharing a projection shares the totals
     it is built on.
   - Linking a gift's cost to a transaction needs only read, and then recategorises the
     transaction as Gifts, with no Activity entry (`ui/gifts.py:562, 594-660`). **Remedy:**
     linking needs write on the account, and is recorded.
   - Typed prices are server-wide: any user with a transaction in an instrument can type one,
     and the last-trade fallback reads every user's trades (`ui/prices.py:302-344`,
     `valuation.py:77-88`). One user's figures move another's, and reveal their price.
     **Remedy:** a typed price is its typer's, used for their accounts, and the fallback reads
     only accounts the viewer can see. **Alternative:** only admins type server-wide prices.
   - A budget built on a read-shared account and shared on re-shares it (C39).
8. **P8 (Low): Activity misses receivers.** Receivers of a projection, tax book, gift or giving
   plan or person see no entries, and nobody sees that their share was removed
   (`ui/activity.py:216-238`), against S10.8. **Remedy:** every kind's receivers see its
   entries, and a removed receiver keeps the one entry that says so.

## 4. The code against the requirements (B)

Each row's remedy follows the requirement unless it says to change the requirement instead.
Each fix of a wrong figure comes with a golden-file test of the case (S17.5).

### 4.1 Wrong figures

| Id | Rank | Requirement | What the code does | Remedy |
|---|---|---|---|---|
| B1 | High | S2.3 average cost | Only the lots a sale consumes are re-based to the average (`ledger/lots.py:394-411`). Run: buy 10 @ $10 and 10 @ $20, sell 5 then 15 at $15: $350 of basis disposed against $300 paid | Re-base every held lot of the instrument in the account at each sale, or keep the pool as one running quantity and basis |
| B2 | High | S3.8.3–4 wash sales | Losses are found on the raw replay (`washes.py:77-79`), so a deferred loss sold again at a loss isn't deferred again. A replacement lot takes the tacked date as `acquiredOn` and FIFO sorts on it (`ledger/lots.py:187-195, 92-97`). Run: a Dec 1 FIFO sale took a Jun 15 replacement before an Apr 1 lot | Find losses on the adjusted replay, repeating until nothing changes; keep `acquiredOn` the day bought, and carry the tacked holding period apart, for the term only |
| B3 | High | S2.5 reinvestment | An OFX reinvestment makes a `dividend` row and a `reinvest` row, both with `dividendType` (`importers/ofx.py:174-184`), and the income panel counts both (`taxes/panels.py:377-379`): $100 shows as $200 of 1099-DIV | The `reinvest` row is the buy alone, with no `dividendType`, and the panel counts dividends once |
| B4 | High | S8 deductions | Whole transactions add `-amount` and splits add `amount` (`taxes/panels.py:561, 569`), and splits carry the negative sign: a $150 Medical split lowers Medical by $150 | One sign for both: splits add `-amount` too |
| B5 | High | S3.2–3.3 options from files | OFX `BUYOPT`/`SELLOPT` become stock buys and sells, `CLOSUREOPT` is dropped (`importers/ofx.py:205-257`), and a CSV's OCC ticker is never a contract (`importers/csvfile.py:268-270`) | Map `OPTBUYTYPE`/`OPTSELLTYPE` to the four option trades and `CLOSUREOPT` to expiry, assignment or exercise; read OCC symbols in CSVs as contracts. **Alternative** until then: refuse option rows, naming them, rather than import them as stock |
| B6 | High | S1.9.1 loan terms | The rate is a `Money` field of two places (`ui/loans.py:34, 46`): 6.875% is refused | A rate type of its own, to three places (four for an ARM's index and margin) |
| B7 | Med-High | S2.3, S2.8 | Imported and synced sales record no lot method (`store/repos/ledger.py:321-341`); changing the account's method rewrites closed years and doesn't recompute wash sales | Record the method in force on every sale, however it arrives; a changed method applies to later sales and reruns wash sales. **Alternative:** a change asks first, naming the closed years it would rewrite (S2.8) |
| B8 | Med-High | S3.8.5.3 | Stock from an assignment is used as a wash-sale replacement (`options/__init__.py:151-165`, `washes.py:58-67`) | Leave assignment and exercise legs out of replacements, and flag them for review as S3.8.5.3 says |
| B9 | Med-High | R3.2, S1.3.3.8.2 | OFX positions add or remove lots instead of being checked (`importers/ofx.py:159`, `ledger/lots.py:451-467`) | Positions in a file are a check, as a statement's are: a difference shows on Reconcile, and the lots change only through transactions |
| B10 | Med | S2.4 | Return of capital skips lots without basis and drops any excess over basis instead of making a gain (`ledger/lots.py:258-263`) | Spread it over every lot by quantity, a lot without basis keeping its share until its basis is entered; an excess over basis is a capital gain |
| B11 | Med | S3.3 | A written option's gain turns long-term after a year (`ledger/lots.py:51-57, 360-363`); IRC §1234(b) keeps it short-term | A written option's gain or loss is always short-term; S3.3 says so |
| B12 | Med | S3.4–3.5 | An assignment's premium is frozen into the lot; deleting an assignment leaves its stock trade; a closed strategy's risk at open is 0; a strategy never closes when its last leg is assigned (`options/__init__.py:169-186`, `ui/transactions.py:733-735`, `options/strategies.py:158-159, 264, 343-359, 511-512`) | Fold the premium at replay; deleting an assignment deletes its stock leg, after asking; keep the risk at open as it was at open; a strategy closes when its last leg closes by any outcome; unlimited risk counts as such |
| B13 | Med | S1.6.2.6 | A coinjoin's fee is taken from the whole transaction, giving a negative transfer out (`bitcoin/sync.py:201`) | The wallet's fee share is its inputs less its outputs, never more than the net out. **Alternative:** a transaction with outside inputs is recorded as its net, marked for the owner to check |
| B14 | Med | S6.3.1 | The bitcoin model replaces the draw for all crypto, not only bitcoin (`projections/__init__.py:231-236`) | Apply the model to the bitcoin holdings only; other coins keep the crypto assumption |
| B15 | Med | S8.6 | IRA and 401(k) limits are checked per account, not per person (`taxes/panels.py:429, 455`) | Sum each person's contributions across their accounts of the limit's kind |
| B16 | Med | S7.8.7, S8.11 | The gift-tax flag misses 529 deposits for anyone without a gift plan, and five-year elections (`gifts/__init__.py:371-381`) | Count every deposit to a beneficiary's 529, plan or not, and spread an election over its five years |
| B17 | Med | S16.11 | A book before the earliest shipped year silently uses 2025's figures (`projections/taxtables.py:164-167`) | Ship the figures for every year a book may cover (ten back). **Alternative:** a year before the earliest shipped has none, and panels that need them say so |
| B18 | Med | S1.11.2–3 | Newest-first CSVs take the day's first row as its last balance, so every busy day mismatches (`ledger/balances.py:58-60`) | Tell a newest-first file by its dates and read it in reverse before taking a day's last balance |
| B19 | Med | S1.3.2, S1.11.5–6 | Re-imports aren't idempotent: sub-cent rounding marks rows changed; FITID rows never fall back to date, amount and payee; a repeated FITID overwrites (`store/repos/ledger.py:302-321`) | Compare rounded amounts with rounded amounts; match a FITID row against rows without one by date, amount and payee; keep both rows of a repeated FITID and flag them as duplicate suspects (S1.11.5) |
| B20 | Med | S1.3.3.1 | A card statement's CR/DR sign is flipped twice (`importers/statements.py:279-283`); OCR reads at most 3 pages (`receipts/ocr.py:19`) | Flip once; read every page within the time limit. **Alternative:** S1.3.3.1 says a scanned statement is read to its third page |
| B21 | Med | S1.9.3, S1.9.5 | A payment not made through the loan's route counts wholly as principal; PMI is charged to payoff (`loans/__init__.py:195-203, 352`) | Split every payment matched to the loan by the schedule, whatever made it; end PMI at 78% of the original value |
| B22 | Low | S1.9, S3.3, S6.7.3, S7.9.3, R3.10 | TXF drops L and C codes; holding periods use "> 365 days" for items and donated shares; the tracking floor widens every band; a portfolio's past figures lose a deleted account; tax due dates skip only weekends | Write L and C; one anniversary rule for every holding period; the floor as a minimum width; keep a deleted account up to its deletion, as budgets do; a holiday table with Emancipation Day |
| B23 | Low | R1.9, S14.3 | Floats in money paths (`assets/__init__.py:141`, `loans/payoff.py:139-147`, price sources' JSON, Bitcoin Core amounts, `projections/__init__.py:272, 449`), and money kept as decimal text, not cents (`store/tables/loans.py`, `assets.py`, `options.py`, `Transaction.proceedsAdjustment`) | Decimal in each path (JSON read with `parse_float=Decimal`), and cents in those tables, by a revision. **Alternative** for projections: C40's exception |

### 4.2 Wrong behaviour

| Id | Rank | Requirement | What the code does | Remedy |
|---|---|---|---|---|
| B24 | Med-High | S11.2 | A pulling side's receipts can't reach the side that serves: `deliver` calls back to fetch them (`links/receive.py:102-136`), fails, and that direction stops for good | The side that pulls sends its receipts' bytes in `deliver`, in parts, and the sequence advances only when they are taken. **Alternative:** S11.2 says receipts need both sides reachable, and a side that can't fetch them takes the rest of the change without them |
| B25 | Med | S11.4, S11.7.1 | Large changes aren't oldest to newest: whole documents are ordered by the newest date anywhere in them (`links/serve.py:380-404`), and one over 20 MB fails the link | Split a document's records by date, so each part is whole records up to a date. **Alternative:** S11.4 says documents travel whole, and the copy is usable once the last part arrives |
| B26 | Med | S11.9.5.3 | A signed but malformed change raises outside the guarded step (`links/changes.py:113-126`), the unlock answers 500, and the inbox stays stuck | Check a change's shape inside the guarded step; one that fails is set aside, recorded on the link, and everything is asked for again |
| B27 | Med | S12.11.2, S13.4 | The alerts run every minute (the sweeper counts as a task end) inside one write transaction that replays every ledger (`runtime.py:39-41, 156-162`, `alerts.py:532`); a failing check resolves its alerts and reopens them, emailing again (`alerts.py:539-592`) | Evaluate in a read transaction and write only what changed; the sweeper doesn't count as a task end; a check that fails leaves its alerts as they were |
| B28 | Med | S14.9.2, S16.1 | In the container the server's time zone is UTC: compose passes no `TZ` or `/etc/localtime` (`timezones.py:11-25`), so backups, summaries and *Auto* users run on UTC | Mount `/etc/localtime` (and pass `TZ`) in `compose.yaml`, and say so in operations. **Alternative:** Settings › General chooses the server's zone, defaulting to the host's |
| B29 | Med | S15.4.7, S14.7 | Host commands reach Activity only at the unlock (`runtime.py:202`); `keys verify` against a running server clears no alert until a restart; `keys init` queues nothing | A task takes the host events every few minutes, as S15.4.7 says; every `keys` and `db` command queues one |
| B30 | Med | S18.3.2, S13.6 | The connector calls `hello` before its socket is up, so with MoneyKata down or locked it crash-loops and can't be unlocked (`mkc/core.py:57-68`, `mkc/main.py:75-79`) | Open the socket first, and retry `hello` with a growing wait; MoneyKata down or locked is a state the connector reports, not a crash |
| B31 | Med | S18.4.2 | A failed `pair` has already written `pairing.json`, destroying a working pairing (`mkc/core.py:85-87`) | Write the new pairing to a temporary file and rename it only once `/pair` succeeds |
| B32 | Med | S10.9.5 | MCP's `list_transactions` takes any `limit`, −1 and 100,000 included (`mcp.py:143`); the instructions call amounts "decimal strings" (`mcp.py:30-34`) | Check `limit` (1 to 500) through the same model as the API's pages, and every tool's input against its schema; correct the instructions |
| B33 | Med | S1.3.3.8, S1.11.7 | Retirement, plan and exchange accounts have no Reconcile tab (`ledger/types.py:108-115`), although their statement checks and overdue alerts point to it | Give the tab to every type that S1.11.7.1 expects statements from (C43). **Alternative:** move the plan-statement check to the Overview, and point the alerts there |
| B34 | Med | S4.4, S4.5 | The refresh asks for every instrument ever traded, and for expired options every day (`prices/refresh.py:141-155, 283-290`); option staleness uses two trading days | Price only what is held or watched, and an option only until its expiry; option staleness as S4.5 says |
| B35 | Med | S1.6.1, S1.6.2.7 | A repeated derived address stops every later wallet's sync (`store/tables/wallets.py:52-57`); one missed read marks a transaction *no longer on the chain*, and Keep is undone at the next sync | Insert addresses with "if absent", and catch each wallet's failure on its own; mark a transaction off the chain only after two reads miss it, and keep Keep |
| B36 | Med | S1.6.3 | Private keys inside a descriptor, and seeds written as a numbered or comma list, are refused only as "Not a bitcoin address" without the reason (`bitcoin/keys.py:275, 306-316`); nothing is stored | Run the secret check on every key inside a descriptor and on the words whatever separates them, in the browser and on the server, and refuse with S1.6.3's reason |
| B37 | Med | various | Edits of a transfer-in never reach holdings (`ui/transactions.py:698-701`); one bad price answer aborts the whole refresh (`prices/refresh.py:307-313`); wallet keys and projection inputs are unbounded and stall the server (`ui/wallets.py:53-55`, `ui/projections.py:199-232`) | Update the transfer-in's lot on edit; count any error from a source as that source's failure for that instrument; cap the keys' length and count, and bound the projection's years (a birth year in the last 120, a horizon of at most 100) |
| B38 | Low | S13.8.4, S13.8.7, S13.8.9 | 52 routes answer 201 and about 8 send `Location`; some 202s carry no job; Reset copy is synchronous; OpenAPI names no release (`contract.py:40-42`) | `Location` on every 201, a job on every 202, Reset copy as a job, the release from `web/VERSION`; a route-walking test for each. **Alternative:** S13.8.4 allows 201 without `Location` for what has no URL of its own |
| B39 | Low | S12, S18 | Settings › Receipts says receipts "go into every backup" (`web/ui/screens/settings.js:265-266`, `web/ui/guides/settings-receipts.md:3-4`); Settings › Imports says "No bank or exchange is connected" (`settings.js:344-345`) | Correct both texts and the guide to S14.6 and S18 |
| B40 | Low | S13.6 | `moneykata.toml` ignores unknown keys (`config.py:274-291`): a `trusted_proxy` typo starts fine and every change is then refused 403 | Refuse to start on an unknown key, naming it, as an unknown section is refused |
| B41 | Low | S11.8, S11.9.4 | A pull records only a count; *Pull now* records no actor; a copy already unlocked takes any words and records an unlock (`links/copy.py:128-130`); a receipt's hash is checked after it has been sent (`ui/linked.py:326-333`) | Record who and which shares; record *Pull now*'s actor; check the words even when unlocked; check the hash before the last chunk goes, ending the response with an error if it fails. **Alternative** for the hash: check it when the file arrives and when it is rewritten, and not when shown |
| B42 | Low | S18.5, S18.9 | The Folder driver runs while locked (`mkc/core.py:248`); a failing Connection alerts only its owner; no report follows a run | Hold the Folder driver while locked, or change the terms (C24); alert admins as well; report after each run |
| B43 | Low | S1.11.2 | Asks for a balance after a fixed 45 days without one, not when a statement or import is overdue (`ledger/reconcile.py:15, 133-138`) | Ask when the statement is overdue (S1.11.7). **Alternative:** S1.11.2 says 45 days |

## 5. Promised, not built (N)

None of these is in `gaps.md` or `later.md`. Most are in no milestone at all: N1–N6, N8 and
N10–N13. The others (N7, N9, N14–N17) fall inside a milestone that S17.9 lists as built, such
as expiry and assignment (S3.4), giving (S7.9), alerts (S12.11) and the API conventions
(S13.8), so they are unfinished parts of it. The README says the seven milestones are built,
and S17.9.8 says the first release is those milestones. So each item here drops out of the
first release without being named (C51). For every item the alternative to building it is the
same: move it to `later.md` with an L id, and trim the requirement to what is built. The rows
say where that would cost more than it saves.

| Id | Rank | Requirement | What is missing | Remedy |
|---|---|---|---|---|
| N1 | High | S2.6, S2.7, S9.8.2.5.3, S10.8, S11.5.2 | Categorisation and payee rules: no table, code or screen; imports apply none, and the receipt reader's merchant is the raw top line | Build before the first release: the rules' table, their screen, applied on import and on demand. Moving it to `later.md` would leave the receipt reader, Activity and links describing something absent |
| N2 | Med | S14.8, S13.7.2 | A user's export of their own data (no route, no ZIP anywhere) | Build as a job that streams the ZIP of CSVs and decrypted receipts straight to the response, with no temporary file, after the password again |
| N3 | Med | S5.1, S5.2.2, S5.2.4, S5.2.5 | A portfolio of chosen holdings; allocation, target, drift and rebalancing; income by month and its forecast; a holding's price chart with its trades | Schedule as a milestone part, allocation and income first. **Alternative:** `later.md`, with S5.2 trimmed to value, returns and holdings |
| N4 | Med | S2.4, S3.10.2 | Symbol changes, spin-offs and mergers (only splits and return of capital) | Build the three as transaction kinds, a spin-off taking a basis split typed by the user |
| N5 | Med | S2.8 | Confirmation before an edit changes a closed tax year's gains | Build: the edit's dry replay names the years whose gains move, and asks |
| N6 | Med | S4.3 | Alpha Vantage and CoinGecko | Build both, or move them to L2's list of sources to try and take them out of S4.3's table |
| N7 | Med | S3.4 | Assignment or exercise with no shares held makes a short stock lot (it makes `sale-without-lot`) | Open a short stock lot at the strike, as S3.4 says |
| N8 | Med | S16.15 | Settings › TLS (in the hand-written mockup, not in the app) | Build the read-only section. **Alternative:** drop it from S16 and the mockup, and show the certificate's names and expiry in Settings › General in `tls` mode |
| N9 | Med | S13.7.5.4, S13.7.6 | `/link`'s 60 calls a minute; 100 MB of uploads in flight per user | Build both, with K22's limit on unsigned calls |
| N10 | Med | S15.6.8, S15.7.2, S16.13, `operations.md` §3 | The unlock's report of what a restored database can't open; re-encryption progress; restoring a `pre-upgrade/` copy (`db restore` takes only a backup folder) | Build the report (a pass over receipts and secrets after a restore), the progress counter, and `db restore` of a pre-upgrade `.db` with its `.keyring`. **Alternative** for the last: operations §3 restores a pre-upgrade copy by hand, step by step |
| N11 | Med | S11.5.1, S11.7, S11.8, S11.9.6.6, S12.10.3.4 | A tax book's files across a link; positions, gains, loans and items in the linked window; "what flows each way" and the last pull; who viewed; the orphan sweeper | Build each. **Alternative:** S12.10.3.4 lists the screens sent, and the rest goes to `later.md` |
| N12 | Med | S10.1.6.4, S10.1.9, S13.7.9 | The email for a recovery-code sign-in; the new-address email for users with two-step (`ui/session.py:227-229`); an Activity entry for opening a written email | Build each; the new-address email by passing the address on the two-step path |
| N13 | Med | S8.16, S9.3, S9.6 | A tax document's file through its tax book (co-filers get 404); receipts on gifts and donations, which show in the Inbox and can't be detached or deleted | Link tax documents, gifts and donations through `ReceiptLink` with their own kinds, give `receipts.level` those kinds, and add detach routes |
| N14 | Med | S6.1.2, S7.9.3 | Projected contributions capped by S1.4's limits; QCDs checked for age, limit and an IRA source | Build both from the tax tables (S16.11) |
| N15 | Low | S12.11.1.3, S15.8.4 | Alerts for an option expiring within a week and a pledge due; the rotation reminder as an alert | Build the three causes in the alerts task |
| N16 | Low | S13.8.3, S13.8.8, S16.10 | Problem types and codes in the OpenAPI document; `Idempotency-Key` beyond `POST /transactions`; Settings › Receipts' allowed types | Generate problem responses and codes into the document; honour `Idempotency-Key` on every create; build the types setting, or drop it from S16.10 |
| N17 | Low | S18.1.2 | A test that fails when a driver reaches a host it didn't declare (the allowlist is one growing set for all drivers) | An allowlist per driver run, and a test that runs each driver with every other host refused |

## 6. Conflicts (C)

Each remedy says which side to change. Where the code already follows one side, that side is
usually the cheaper one to keep, and the remedy says when it isn't.

### 6.1 Secrets, keys and copies

| Id | Where | Conflict | Remedy |
|---|---|---|---|
| C1 | S9.7 vs S14.6, S16.12 | "Backups include the receipts directory" vs a backup is "the database with its keyring, and nothing else". The app's own Settings text sides with S9.7 (B39) | Correct S9.7 to S14.6, and the app's text with it. **Alternative:** put receipts into backups and rewrite S14.6, at the cost of backups as large as the receipts |
| C2 | S14.6 vs S9.2, S15.7.2 | Receipt files "written once and never changed" vs a re-encryption rewrites each (K9) | S14.6 says a re-encryption rewrites them, and K9's remedy keeps a restore whole |
| C3 | S9.7 vs S14.10.5 | A file "stays while any receipt row names its hash, deleted or not" vs pruning removes it "once none of them needs it"; the code follows S9.7 and marks a live receipt *File pruned* while the file stays | Keep S14.10.5: a file goes when no live receipt needs it, deleted rows not counting; correct S9.7 and the code. **Alternative:** keep S9.7, and pruning marks a receipt pruned only when its file is gone |
| C4 | S15.5.1, `operations.md` §6.2 vs S14.6 | "Restore the backup … Nothing is lost" vs a backup holds no receipt (K9) | S15.5.1 and §6.2 restore `receipts/` from the host's backup of the same moment, before `db restore` |
| C5 | S15.6.8 vs S14.6, `operations.md` §6.1 | The restore moves "the receipts" aside vs it leaves them in place, which the code does (`store/copies.py:193-203` still rewrites receipts inside `before-restore-*/`) | Correct S15.6.8, and remove the receipts step from the copies' code |
| C6 | `operations.md` §2, §2.1, §2.2 vs S14.6 | Put `backups/` on another disk or pool vs it "belongs inside what the host backs up, not on a disk apart" | Operations follows S14.6. **Alternative:** S14.6 adds that a second copy off the host is welcome, as long as the phrase never goes with it |
| C7 | S15.3.1 vs S15.7.2, S15.7.1.1 | The phrase is "never sent over the network beyond the unlock request" vs Re-encrypt sends it from the browser and `keys rotate` sends the new one | S15.3.1 names the three times the phrase crosses. **Alternative:** Re-encrypt becomes a host command (K5), and only the unlock and the rotation's own socket carry it |
| C8 | S15.1.7 vs S15.4.2 | The `tls/` pair "protects the listener, not the data" vs it carries the phrase in `tls` mode (K10) | S15.1.7 says the pair protects the phrase in transit, and K10's remedy follows |
| C9 | S15.1.7, S16.2 vs code | Each written email "holds a link that is a one-day token" vs invitations last 7 days (`auth/users.py:26`), so an invitation's file is gone (after 25 h) while its link still works | Keep each written email as long as its link works (a week for an invitation). **Alternative:** invitations last a day, as the other links do |
| C10 | S16.14 vs S13.6, S15.4 | Network ranges for `/ui` vs a locked server can't read them (K23); the text now says so (A14), the behaviour is still to decide | K23's remedy, or keep A14 as written |
| C11 | S16.13 vs S15.8.4; S12.11.1.1 vs S15.6.5 | Key storage "read-only" vs a configurable reminder; the phrase check counts only `keys verify` vs "every unlock is a check as well" | S16.13 says "read-only but for the reminder"; an unlock counts as a check, in the alert and in Key storage. **Alternative:** S15.6.5 drops "every unlock is a check" |
| C12 | S16.13 vs S15.4.7; S14.1.3 vs S15.4.1 | "Who confirmed the phrase" vs host commands have no who; the pre-upgrade copy is made "at start" vs at the unlock | S16.13 shows "on the host" for a host command; S14.1.3 says "at the unlock" |
| C13 | Rejected ideas 1–2; S17.8.3 | Argue from "the key file", and "operations.md covers … the key directory", against R1.13 and rejected idea 18 | Rewrite the two reasons around the phrase held in memory, and drop "the key directory" from S17.8.3 |

### 6.2 Links, the connector and the network

| Id | Where | Conflict | Remedy |
|---|---|---|---|
| C14 | S11.9.1 | Its first sentence says `links/<link-id>/`; its tree says the folder is "named at random, never by the link's id" | The first sentence says `links/<random name>/` |
| C15 | S13.7.6 vs `link-protocol.md` §1.4 | JSON bodies up to 1 MB vs a link's up to 20 MB; resolved in the text by A11 | None further |
| C16 | S11.2 vs `link-protocol.md` §4.4 | Either side reaching the other is enough vs receipt bytes are "fetched on their own", which needs the receiver to reach the source (B24) | B24's remedy, which keeps S11.2 true |
| C17 | `link-protocol.md` §1.3, §7 vs S13.6, S13.7.5 | Every answer signed, refusals 403 or 426 vs an unsigned 503 `locked`, and 429 with no code | The protocol lists the unsigned 503 `locked` and a signed 429 `limit` with `Retry-After`, and says a caller treats both as "try later" |
| C18 | R3.4, S11.9.7 vs S11.4, S11.7.2 | A revoked share ends "on the next request" and "at once" vs "at the next pull"; a receiving admin's repeated Pause holds a revocation or an End link off indefinitely | R3.4 and S11.9.7 say a revocation reaches a linked server at its next exchange; a Pause stops data, never removals or an end, which still cross |
| C19 | `link-protocol.md` §4.4.1 vs S11.4, S12.10.3.4 | "The latest 500 transactions" vs a first snapshot that fills from the earliest records, and every screen as its owner sees it | Send the whole history, in parts by date (B25). **Alternative:** S11.4 and S12.10.3.4 say a linked window shows the latest 500 transactions per account |
| C20 | S11.3, S11.1.2 vs `link-protocol.md` §4.1 | User lists "at every pull", after approval, vs both lists cross in `join`, before it (P5) | `join` carries no user list; lists cross from the first exchange after approval |
| C21 | S10.10.1 vs S10.10.2, S10.10.3 | A remote user adopts a same-named person, filled from its server, vs a person changed only by itself, its creator or an admin, and a private match shows *Ask to share* | S10.10.1 follows P5's remedy |
| C22 | `link-protocol.md` §1.2, `connector-protocol.md` §1.2, §3.3 vs the transport | "A server pretending to be MoneyKata gets nothing past it: no report, no file" vs request bodies sent under unverified TLS before any answer is checked (K3) | K3's remedy, and both protocols then say TLS is verified and what the signatures add |
| C23 | `connector-protocol.md` §4, §4.1.2, S18.4.2 | `hello` was `{protocol, version, fingerprint}` (A20 adds `key`), and §4.1.2 checks "the key it answers with" vs the code checks only the `fingerprint` field (K3) | The code checks the key, as §4.1.2 says (K3) |
| C24 | S18 terms vs S18.9.1 | "Locked, it reports and nothing more" vs the Folder driver needs no vault (B42) | Hold the Folder driver while locked, keeping the terms. **Alternative:** the terms say a locked connector runs only drivers that need no credentials |
| C25 | `connector-protocol.md` §4.2.2 vs S18.6 | `removed` includes Connections "whose accounts all turned sync off" vs Connections independent of accounts until removed | §4.2.2 follows S18.6, which the code does |
| C26 | R3.1 vs S18 | The only outbound calls are price sources, the bitcoin explorer or node, SMTP and links, each in Settings vs the connector's institutions, which no Settings screen lists | R3.1 names the connector's calls, and Settings › Connector lists each Connection's host |
| C27 | S18.4.4, `operations.md` §10 vs S18.2.2 | The connector deletes its credentials on a MoneyKata-side Unpair vs MoneyKata has nothing to call, and no mechanism is stated (K20) | S18.4.4 says a signed `not-paired` answer is the signal (K20) |
| C28 | S13.5 vs S16 | Hosts "allowed by name" vs no list in Settings to name them in; the code counts every admin-entered host, and peers' link hosts (K18) | S13.5 says which hosts count as named (the Email and Bitcoin hosts), and that a peer's never does (K18). **Alternative:** a list of allowed names in Settings › Network |
| C29 | S11.2 vs S16.9; S17.6; S17.2.1 | The link address set in Settings › Linked servers vs S16.9 doesn't list it; `web/dev.sh`'s list omits `vendor`, `audit`, `base-update`, `mocks`; the register "records the hashes" vs `docs/dependencies.md` says `web/audit.json` does | Add the link address to S16.9, the four commands to S17.6, and `web/audit.json` to S17.2.1 |
| C30 | `connector-protocol.md` intro; §3.1, §3.2; §4.3.1 | Names `connector/core/` (it is `connector/moneykata_connector/`); sends the protocol version to "section 7" and the codes to "section 8" (they are §5 and §7); "its fingerprint" without saying which key's | Correct the path and the two references, and say "the identity key's fingerprint" |

### 6.3 Users, sharing and the rest

| Id | Where | Conflict | Remedy |
|---|---|---|---|
| C31 | R1.9 vs S13.8.2.1, S14.3 | Amounts are "strings in JSON" vs exact JSON numbers, which the code writes; `money.py:1-2`, the MCP instructions and import job results still say or send strings | R1.9 says exact JSON numbers; correct the docstring and the instructions, and send numbers from the import jobs |
| C32 | R1.6, S10.2 vs S16.2, S10.1.6.4 | Admins can't see money vs Open shows reset links and admins reset two-step (K8) | K8's remedy or its alternative |
| C33 | R1.8, R1.22, R2.9, R3.4 vs S10.3, S10.10.2, S11.3 | Accounts and portfolios, one way, to "a linked server", "one account or portfolio" vs seven kinds to named users both ways; R1.22 lists *person* where S10.3's table has *gift plan*; the code has eight kinds (`ui/sharing.py:19-21`) | One list of kinds, S10.3's table with *person* added as the code has it, and R1.8, R1.22, R2.9 and R3.4 referring to it and to named users. **Alternative:** person is not a kind, and its privacy works through *Ask to share* alone |
| C34 | S8.14.3 vs S10.3.3 | A tax book is "never [shared] to a linked server" vs "any of the seven kinds" | Keep S8.14.3, and S10.3.3 names the exception (P7). **Alternative:** drop the exception, for the preparer of S11's opening |
| C35 | S10.1.1 vs S13.7.3 | "The only password rule is a minimum length" vs the common-password list (and the code's 1,024-character maximum) | S10.1.1 refers to S13.7.3 for the rules |
| C36 | R3.5 vs S1.6.2.1, S16.7 | The bitcoin explorer "off until configured" vs mempool.space by default; the code reaches it as soon as anyone makes a wallet (`bitcoin/sync.py:51-56`) | Keep R3.5: no wallet is read until an admin saves Settings › Bitcoin, mempool.space being the suggestion there. **Alternative:** R3.5 says the public explorer is the default, and the wallet form says its addresses go to it |
| C37 | S13.7.5.1 vs S10.1.5; S10.1.9 vs S10.1.6.4 | Reset requests "fail" vs they always answer the same; the email list omits the recovery-code sign-in | S13.7.5.1 counts reset requests, not failures; S10.1.9 adds the recovery-code email |
| C38 | S11.8 | Views recorded "as for any account", but no requirement records views of an account | Drop "as for any account" and say what a linked view records. **Alternative:** S10.8 records views of shared accounts too |
| C39 | S7.1.1 vs R3.4, S5.1.1 | A budget counts its accounts' transactions "whoever can see them", so a read-shared account in a shared budget is re-shared; portfolios do the opposite | A budget's receivers see the actuals of the accounts shared with them, as portfolios do (S5.1.1). **Alternative:** R3.4 says a budget shares the totals of the accounts it is built on, and the Share dialog says so |
| C40 | S6.9 vs R1.9, S13.8.2.1, S14.3 | NumPy models vs no amount through a float; the projection's start value and tracking points go out as floats | S6.9 states the exception: the models run in floats, their results rounded to cents and sent as exact numbers; the start value and tracking stay Decimal |
| C41 | S6.3.1 vs S6.4.2.3; S6.4.2 vs S6.4.2.1 | A range per bitcoin model vs crypto volatility spreads it (the code); "normal or log-normal" vs log-normal | S6.3.1 says the crypto volatility spreads every model, and S6.4.2 says log-normal |
| C42 | S10.10.4 vs S8.14.1, S3.8 | A user adds relationships they are in, alone, vs the spouse decides joint tax books and wash sales for both (P1) | A spouse needs both people's confirmation; until then the marriage counts for gifts only |
| C43 | S1.11 vs S1.3.3.8, S1.11.7.1 | Reconciliation for "banking, card, brokerage-cash and loan accounts" vs plan statements checked on the Reconcile tab and overdue alerts for IRAs, HSAs, 401(k)s, 529s and DAFs (B33) | S1.11 covers every account kept from files or statements (B33) |
| C44 | S1.3.3.3 vs S1.3.3.4 | Lines already present start left out vs left-out lines teach skips, so a statement read beside its OFX teaches that "debit card purchase" lines vanish (the code does, `importers/statements.py:368-384`) | S1.3.3.4: a line left out because it was already present teaches nothing; the code follows |
| C45 | S4.3 vs S12.11.1 | A statement value older than 90 days "raises an alert" vs no such cause, and none in the code | Add the cause to S12.11.1.2 and build it. **Alternative:** S4.3 marks it stale without an alert |
| C46 | S3.8 | An IRA counts as a replacement and the loss is added to its basis vs Rev. Rul. 2008-5: the loss is lost, with no basis increase | S3.8.3 states the exception, and the code follows |
| C47 | S3.10.1 vs S4.5; S2.1 | "Strike ÷ the ratio" with no rounding vs strikes in thousandths (`options/adjust.py:129` writes 283.333…); S2.1's classes omit `money-market`; the stored option symbol matches neither S2.1 form | S3.10.1 rounds to the thousandth, as OCC prints; S2.1 adds `money-market` and names the stored form |
| C48 | S7.9.3 | Donated shares under a year deduct "the basis" vs the lesser of value and basis, which the code does (`ui/giving.py:519`) | S7.9.3 says the lesser of value and basis |
| C49 | S9.8.3 vs S13.5; S9.8.4.2 vs S9.1, S9.5 | The egress guard "would refuse" a model download vs it sees only the server's own clients; a worker so a hostile file can't take the server down vs thumbnails and HEIC in the request (K4) | S9.8.3 says the reader has no network (K4); thumbnails and HEIC move into the worker (K4) |
| C50 | S8.1 | Form 8949 boxes A–F, while the code expects 1099-DAs; the 2025 form's digital-asset boxes should be checked (not verified here) | Check the 2025 form; if it has digital-asset boxes, S8.1 adds them and the panels route 1099-DA sales there |
| C51 | S17.9.8 vs the sections | "The first release is the seven milestones" vs the parts no milestone schedules (section 5) | Schedule section 5's items as a milestone before the first release, or move each to `later.md`; the README's status then names what is left |
| C52 | S12.11.1.3 vs S10.10.3 | A share request alerts "each user" vs the creator and the admins, which the code does | S12.11.1.3 names the creator and the admins |
| C53 | `operations.md` §2, §5.1 | §2.3 comes before §2.2; §5.1's "stays locked" table repeats refused-start rows ("data directory is in use") | Swap §2.2 and §2.3, and move the row to the refused-start table |

## 7. Requirements written from the code, for review (A)

What the code does that no requirement described, now written into its section. Each entry
describes the code as built. Where this review asks for a change, the entry names the
finding, and the requirement should be rewritten when that finding is settled. Open
question **Q19** (`questions.md`, and the requirements' README) holds the confirmation of the
whole list, so it is tracked with the requirements. **The remedy for each entry** is Q19's
answer: confirm it as written, or, for an entry with a *See*, rewrite it with the change that
finding proposes (its alternatives included). An entry without a *See* describes behaviour
this review found no fault with, so confirming it is the expected answer. No entry adds a screen, field, button,
dialog or state, so the hand-written mockup is unchanged. The reset link's hour is already on
its Forgot password card. Its Alerts screen shows sample alerts, not every kind, so A16's three
need no sample of their own; two of them already appear elsewhere in it (the node's
certificate dialog, the *no longer on the chain* mark).

| Id | Item | What it now says | Code | See |
|---|---|---|---|---|
| A1 | S10.1.1 | A username is 2–32 lowercase letters, digits, dots, dashes or underscores, starting with a letter or digit; usernames and emails match without regard to case; a display name is at most 80 characters, an email at most 254 | `auth/users.py:30-31, 211-244` | |
| A2 | S10.1.3, S10.1.5 | An invitation works once for 7 days, a reset link for an hour, an email-change link for 24 hours; a new link of a kind ends the previous one; an admin corrects a user's email only until they join | `auth/users.py:26-28, 261-264, 633-665` | C9 |
| A3 | S10.1.7 | Asking to be reactivated takes the username and password | `auth/users.py:605-631` | K17 |
| A4 | S13.7.1 | The cookie lasts the absolute lifetime; a password change gives the browser that made it a new session and ends the others; accepting an invitation signs in and a reset doesn't; the new token at a change of privilege starts its own absolute lifetime | `middleware.py:309-312`, `ui/profile.py:257-267`, `ui/session.py:437-447`, `auth/sessions.py:70-74` | K7 |
| A5 | S13.7.3 | A password is at most 1,024 characters | `auth/passwords.py:32` | C35 |
| A6 | S13.7.5.5 | The counters are in memory, so a restart clears them | `ratelimit.py:1-3` | K16 |
| A7 | S13.3 | From a trusted proxy, `X-Forwarded-For`, `-Proto` and `-Host` are believed; the client is the right-most address that isn't a trusted proxy; `[server] host` sets the listening address | `middleware.py:87-108`, `config.py:291` | K1 |
| A8 | S13.4 | An hourly prune removes expired sessions and one-time tokens (`schema.md` §4.4.1) | `runtime.py:76-82` | |
| A9 | S13.5 | An outbound call connects within 10 s and waits at most 20 s for each read; an answer that announces more than 20 MB is refused, and price sources stop reading at 20 MB; SMTP waits 20 s | `net.py:13-14, 105-109, 129-139`, `mail.py:63` | K18 |
| A10 | S13.6 | `/healthz` answers 503 `starting` between the unlock and readiness; `GET /ui/api/unlock` tells anyone whether the server is locked, the fingerprint its keyring is wrapped under, and the version | `app.py:150-158`, `ui/unlock.py:47-57` | |
| A11 | S13.7.6 | A linked server's JSON bodies up to 20 MB | `middleware.py:36, 214-220` | C15 |
| A12 | S15.1.7, S16.2 | With a host set, each email waits in `outbox/` in the data directory, in the clear, until it is sent; one the server refuses is set aside there and kept | `mail.py:209-233, 262-266` | K15 |
| A13 | S15.3.5, S15.7.2 | Each keyring names its data key by id as it names its master key; a re-encryption writes its new keyring first as `keyring.next`, which replaces the keyring when the job ends; at an unlock, a `keyring.next` the database does not open with is a re-encryption that never began, and is removed | `keys/master.py:44-47`, `store/maintenance.py:51-53, 100, 181-186` | K5, K6 |
| A14 | S16.14 | An address outside a path's ranges is answered 404; while locked the ranges can't be read, so the locked screen and the unlock answer any address that reaches the listener | `middleware.py:140-173`, `app.py:107-116` | K23 |
| A15 | S16.3, S16.5, S16.8, S16.9, S16.10, S16.12, S16.16 | Each setting's bounds and defaults: idle 1–168 hours, absolute 1–365 days, lockout 3–100 failures for 1–1,440 minutes; minimum password 8–128; imports 1–200 MB; release after 5 minutes to 24 hours; receipts 1–100 MB and 1–4 jobs; backups at 02:30 with 14 kept (1–365); alerts after 1–336 hours | `settings.py:201-260` | |
| A16 | S12.11.1.1, S12.11.1.2 | The bitcoin node presenting another certificate (admins, S1.6.2.4); a recorded wallet transaction the chain has dropped, and an option past its expiry that wasn't settled on its own (owner) | `alerts.py:92-133, 417-445` | |
| A17 | S18.2.1, S18.3.1, S18.3.2 | The connector's files, modes, socket and variables; the vault's format and how its key is derived; `lock` and `status`, the image's health check | `mkc/vault.py:20-38, 134-186`, `mkc/keys.py:77-88`, `mkc/sock.py:16-23`, `mkc/main.py:17-18, 150-159`, `connector/Dockerfile:20-34` | |
| A18 | S18.2.2, S18.8 | The connector follows no redirect and waits 60 s; files waiting are held in memory, a restart fetches again and the import drops repeats, and a file refused for another reason is dropped, its Connection showing the refusal | `mkc/client.py:51-70`, `mkc/core.py:296-314` | K24 |
| A19 | S18.9.1–3 | Each driver's schedule and limits: the Folder driver every 5 minutes, the folder's own files, `.ofx .qfx .csv .pdf` up to 25 MB, hidden files skipped, a file posted again only when its size or time changes; OFX daily, `https` only, OFX 1.0.2, 45 days (90 while no account matches), codes 15500–15503 as *needs a sign-in*; Schwab daily, 45 days, the callback `https://127.0.0.1`, an access token used until a minute before it runs out | `mkc/drivers/folder.py:16-34, 75-91`, `ofx_direct.py:14-19, 60-95`, `schwab.py:18-22, 199-251` | |
| A20 | `connector-protocol.md` §4, §7 | `hello` answers `key` too; the codes the code uses (`not-found`, `address-invalid`, `too-large`, `locked`, `limit`, and the connector's `fingerprint-mismatch`, `answer-unsigned`, `code-invalid`, `not-moneykata`) | `connector/routes.py:65-93, 157-158`, `mkc/client.py:115-121` | K3 |
| A21 | `link-protocol.md` §1.4, §4, §4.2, §4.4, §7 | Timeouts and ceilings; `hello` answers `key`; `POST /link/v1/file`; the directory's field limits; a large change's parts kept in memory; `not-linked` ends the link here; pulls before the access key exists; `not-shared` and `answer-unsigned` | `links/routes.py:82, 184-208`, `links/client.py:66-101`, `links/manage.py:209-226, 331-347, 416-435`, `links/receive.py:56-57, 64` | K3 |
| A22 | S1.7 | Opposite amounts of cash, not trades, in two of the owner's accounts within 4 days are linked as a transfer, the closest in date; when two are equally close neither is, and the owner links one | `ledger/transfers.py:6-29`, `store/repos/ledger.py:181-204` | |
| A23 | S1.3.2, S1.3.3.8.1 | An OFX file holds one account's statement, and one with several is refused; the value check is within half a percent or $1, whichever is more | `importers/ofx.py:80-86`, `ledger/reconcile.py:158` | B43 |
| A24 | S1.6.1.2, S1.6.1.4, S1.6.2.6 | A check extends derivation at most ten rounds; a multisig descriptor has at most 15 keys; a transaction its owner deleted isn't recorded again | `bitcoin/sync.py:25, 79, 184-190`, `bitcoin/descriptor.py:209` | B35 |
| A25 | S1.9.1, S1.9.2 | The term is 1–600 months and the rate 0–40%; interest is rounded half up to the cent; a balance under $1 left by rounding goes with the last payment | `loans/__init__.py:47-48, 348`, `ui/loans.py:310-327` | B6 |
| A26 | S3.3, S3.6 | Closing trades and expiries take option lots oldest first, whatever the account's method; an expiry is decided on the expiry day's close or one up to four days before it, the user asked when there is none; a close at the strike counts as out of the money | `ledger/lots.py:309, 342-345`, `options/__init__.py:242-245, 274-278` | |
| A27 | S4.4 | History is backfilled from a week before an instrument's first transaction, at most five years back; SPY, VT and BND are always loaded, as the benchmarks | `prices/refresh.py:28-29, 270-278` | |

## 8. Candidate gaps

Each would take the next free id (G25 onwards) when recorded. **Remedy** for each: record it
in `gaps.md` with its rank, then specify it in its section from the finding named, choosing
between the finding's remedy and its alternatives, and remove the gap once specified.

1. **(High) How host commands reach the running server**, and what authenticates them: K1, K6.
2. **(High) What the reader's sandbox is**, and moving all parsing of uploads into it: K4.
3. **(High) How links and the connector verify TLS**, and whether link changes are sealed end to
   end: K3.
4. **(High) Key operations as a journal**: what each step records, and what a failure leaves: K5.
5. **(Med) Restoring receipts**: their key across a re-encryption, and on a new host: K9.
6. **(Med) An unlock passphrase** beside the recovery phrase, or the decision to keep one secret
   (then a rejected idea, with its reason): K10.
7. **(Med) What admins are trusted with**, written into S10.2: K8.
8. **(Med) Who may use the watched folder**: P4.

## 9. Checked and sound, so not raised

- **The key hierarchy as built matches S15.3**: the three levels and their HKDF labels; random
  96-bit nonces under per-secret keys with record-and-field associated data; the keyring's
  associated data bound to the master key id; the manifest's MAC compared in constant time
  (`store/maintenance.py:326`).
- **The streaming file format** of S11.9.6: a one-time X25519 key per file, counter and
  last-chunk nonces, associated data naming the file. No path on disk is chosen by a peer.
- **SQLCipher** runs with `secure_delete` on and temporary storage in memory.
- **The reader** starts as a fresh process (`spawn`), so it inherits no key; receipts reach it
  over a pipe, never a temporary file.
- **Signed requests** cover method, path and query, body hash, time, nonce and the receiver's
  fingerprint, for links and the connector; the 120-second nonce window covers the ±60 s
  clock allowance. Domain separation between `MK-LINK-1` and `MK-CONN-1` holds.
- **The sealing key's private half** is in the vault, `pairing.json` holds only its public
  half, and a box is withheld while the connector reports locked (review 1's F2). A credential
  is compared with its bound host before every run, and the Folder driver's folder is resolved
  inside `/watch` (F3). A pairing is trusted only once confirmed (F7, defeated only by K3).
- **Uploaded files** are typed by their content, never SVG or HTML, and local receipts are
  served with `nosniff`, a sandbox CSP and `no-store`.
- **Validation errors** neither echo nor log what was sent; wrong phrases lock out by address.

## 10. Suggested order

1. **K1, K2 and K3**, then **K4**: the first three are one request away for someone already
   near the server or on the path, and K1 and K2 are small changes in the code.
2. **K5, K6, K9**: write S15.7 and the restore as a journal before anyone re-encrypts for
   real; until then, say in Settings › Key storage that Re-encrypt is not for use.
3. **K7, K8, K13, K14, P1–P5**: access that the requirements mostly already forbid; S10.2
   (K8), S10.10.1 (P5) and S18.9.1 (P4) change with them.
4. **N1** and **B1–B6**: wrong figures in taxes and lots, and the rules the screens assume.
5. **K10, K11**: decide the unlock passphrase and the rotation's meaning, and update S15 and its
   mockup together.
6. The conflicts in one sweep, section by section, then **Q19**'s confirmation of section 7.

## 11. Decisions

The open items were walked through one at a time and each was decided, then approved together.
What each decision wrote is in the requirements, the protocols, `operations.md`, `later.md`,
`rejected-ideas.md` and the hand-written mockup; the code follows in milestone 8 (S17.9.8).

1. **K10, the everyday unlock:** the recovery phrase stays the one secret. Phrases are shown and
   read on the terminal only (`keys init` and `rotate`, the connector's `init` and `reset`); the
   locked screen's field turns autocorrect, autocapitalize, spellcheck and autocomplete off,
   masks the words in every desktop browser and keeps its eye toggle; the locked screen and
   `keys unlock` are equal ways in; `tls` mode looks the same and S15.1.7 says it is for testing.
   The unlock passphrase is rejected idea 20. There is no phone support yet, so S15.4.2 no
   longer argues from a phone.
2. **K11, rotation:** every rotation re-encrypts (S15.7.1, S15.7.3, S15.8).
3. **K8, admins:** admins are trusted operators (R1.6, S10.2); opening a written email is
   recorded in Activity for its addressee. Keeping admins out is rejected idea 23. K13 and K14
   stay, for a stolen admin session.
4. **K3, transport:** TLS is verified, a certificate of a server's own pinned through its code
   and renewed by a signed announcement; signed answers name the caller and the request; only
   `link-ended` ends a link; link changes and receipts are sealed end to end to the receiving
   copy's key. Since no release has spoken the link protocol, this revises protocol 1 rather
   than adding a version (`link-protocol.md` §1, §3.3, §4.1–4.5, §7; `connector-protocol.md`).
5. **K5, K6, K9, re-encryption and restores:** a journal; re-encryption only while the server
   isn't serving, at an unlock or on the host (Settings › Key storage › **Re-encrypt at the next
   restart**); a file or secret that won't open is set aside; host commands take the lock; a
   restore re-wraps the receipts to the backup's key and asks before reviving an earlier phrase;
   the new-host runbook restores the receipts. Re-encrypting while serving is rejected idea 22.
6. **P4, the watched folder:** the Folder driver is dropped; what can't be fetched is uploaded by
   hand (S18.9). Rejected idea 21. K21, P4, C24 and B42's first part go with it.
7. **Item 9:** pruning stays by hand, a shared file prunable once no live receipt needs it (C3);
   a written email is kept as long as its link works (C9); eight shareable kinds, *person*
   among them (C33); a tax book may go to a linked server, read only (C34); no wallet is read
   until an admin saves Settings › Bitcoin (C36); a shared budget shows the owner's own accounts
   and an account shared with the owner only if it is shared with the receiver too (C39).
8. **10a, 10b:** host commands over a Unix socket (K1), and the reader's sandbox (K4), in
   milestone 8.
9. **11a, 11b:** Form 8949's digital-asset boxes G to L from 2025 (S8.1, C50); the connector
   reports every 15 seconds while a sign-in waits (S18.5). Sources are cited in S8.1 and
   S18.9.2 and kept in `docs/external/`.
10. **The parts never built (N, C51):** milestone 8 builds N1, N4, N5, N7, N9, N10, N12, N13, N15,
    N17, N11's sweeper and view audit and N16's problem types; later work L4 to L9 takes N2, N3,
    N11's rest, N14, N16's `Idempotency-Key` and N6; Settings › TLS (N8) and Settings › Receipts'
    types are dropped, the listener shown in Settings › Network instead.
11. **Q19:** A12 becomes an email queue in the database, A26 an expiry decided on the expiry day's
    close only; A2, A13, A17, A19, A20 and A21 follow the decisions above; A10 and A14 are kept;
    the other seventeen are confirmed. Q19 is closed.
12. **Everything else** keeps the remedy this review recommends, with one exception: K23's
    third point takes its alternative (S11.9.10 no longer claims protection from this server's
    admin), since item 3 makes admins trusted.
13. **Order:** these requirement changes first, in one commit, then milestone 8 in its nine
    parts; `initial-code` merges into `main` after milestone 8 (Q15).

## 12. Where things stand, for the next review

Sections 1 to 10 describe the code at `294792b`; their file and line references are to that
commit. This section says what has become of each finding since. Each one was checked against
the code at `328589f`, not taken from the commit messages, which in places claim more than
was built (part 9's "the rest of the review's findings" among them); the rows still open then
were built in milestone 9, which no review has checked yet. Paths are relative to
`web/server/src/moneykata/` unless they say otherwise, and are at `328589f`.

### 12.1 What changed after the review

1. **`f3a4d50`**: section 11's decisions written into the requirements, the protocols,
   `operations.md`, `later.md`, `rejected-ideas.md` and the hand-written mockup.
2. **Milestone 8** (S17.9.8), nine parts, each with its tests:

   | Commit | Part | Findings it took |
   |---|---|---|
   | `313e27e` | 1: access, host commands over the server's socket | K1, K2, K6, K7, K8, K13, K14, P1–P3, P5, P6 (in part), P7 |
   | `20944e9` | 2: transport, TLS verified and pinned, link changes sealed end to end | K3, K18, B24 |
   | `d15ff28` | 3: the reader's sandbox, every file brought parsed in it | K4 (in part) |
   | `5779299` | 4: key operations, a journaled re-encryption that never runs while serving | K5, K6, K9, K10, K11, N10 |
   | `2e1a767` | 5: figures, and Form 8949's digital-asset boxes | B1–B23, C50 |
   | `351f335` | 6: categorisation and payee rules | N1 |
   | `3ee3dbc` | 7: corporate actions, closed years, and the rest promised | N4, N5, N7, N9, N11 (sweeper, view audit), N12, N13, N15, N16 (in part), N17, K22 (in part) |
   | `b14b5cb` | 8: the connector, its Folder driver gone | K12 (in part), K20, K21, K24, P4, B30, B31, 11b |
   | `d7e2a08` | 9: the remaining findings, the generated mockup, both images | P7, P8, B25–B29, B32–B43 |

3. **Decided after milestone 8**, each written into the requirements and the mockup with its
   code:
   - `328589f`: a driver's size is tracked green, yellow or red in `connector-protocol.md` §6,
     and the core has no limit (S18.1.2); an edit made anyway to a closed year stays on the tax
     book until an amended federal return or *No amendment needed* settles it, and a year whose
     amended return is being prepared is open (S2.8, S8.15); admins are alerted while reading
     runs without its file sandbox, on a host without Landlock (S9.8.4.2, S12.11.1.1).
   - `b7b95b4`: an admin who owns what failed (their Connection, their wallets' explorer or
     node) has one alert, the owner's, on screen and by email (S12.11.2); the mockup's help
     says a tax book may go, read only, to a linked server (S8.14.3); an edit's change to the
     realized gains is kept in cents, as all money is (revision 0024, S14.3); this section.
4. **Milestone 9** (S17.9.9): every row 12.2 found still open, in nine parts: `7ee1789`
   (sign-in), `ab9dc23` (emails), `42a225b` (the connector), `ce12371` (links), `d678e48`
   (the host and the reader), `6847ba9` (figures), `c8fd790` (imports, wallets, alerts and the
   contract), `1563bd5` (tests), and the ninth with the generated mockup, both images and
   this section brought up to date. Revisions 0025 (the email queue) and 0026 (the last money
   in cents).

### 12.2 Every finding, by state

- **Done** as the remedy or the decision says: K1–K3, K5–K11, K13, K14, K18, K20, K24; P1–P3,
  P5, P7, P8; B1–B21, B23–B32, B34–B40 and B43 (B20 and B38 done differently),
  and B42 but its first part; N1, N4, N5, N7, N9, N10, N12, N13, N15, N17; C1, C2, C4, C6–C8,
  C10, C12–C16, C19–C22, C25–C30, C32, C34, C35, C37–C43, C48–C53; and A1–A11, A13–A25, A27,
  confirmed or changed as section 11 says (K8, C7 and C24 the decided way, not the remedy).
- **Dropped by a decision**: K21 and P4 with the Folder driver (rejected idea 21), with B42's
  first part; N8, Settings › TLS.
- **Moved to later work** (`docs/requirements/later.md`): N2 (L4), N3 (L5), N11's linked
  window and tax-book files (L6), N14 (L7), N16's `Idempotency-Key` (L8), N6 (L9).
- **Open at the handover, built in milestone 9** (S17.9.9): the table below, each row as the
  check found it and the part that built it. In most the requirement already said what to
  build and only the code was missing.

| Id | Rank | What was missing | Built in milestone 9 |
|---|---|---|---|
| C23 | — | The connector never hashes the key `hello` answers with: it compares the fingerprint `hello` states with the code's, then trusts `client.server_key(hi)` as sent, at pairing and when it reattaches (connector `core.py:77-80, 103-109`); `connector-protocol.md` §4.1.2 says it refuses a key that doesn't hash to the code's fingerprint. The link side hashes it (`links/manage.py:244`) | part 3, `42a225b` |
| K4 | High | A scanned PDF's pages are rendered at 300 DPI with no pixel cap (`receipts/ocr.py:178`); S9.8.4.3 caps a page at the images' 40 million pixels | part 5, `d678e48` |
| K15, A12 | Med | Emails still wait in `outbox/` in the clear (`mail.py:232`), and a refused one is kept whole for ever (`mail.py:257-266`); S16.2 and S15.1.7 say a queue in the database, each removed when sent or when its link expires, a refused one keeping only its recipient, subject and error. No table for it in `docs/schema.md` | part 2, `ab9dc23` |
| K16 | Med | Nothing of the remedy: the pending two-step token survives wrong codes, the sign-in lockout counts the exact address (`ui/session.py:148`; only the separate throttle counts the /64), two guesses on one token can run at once, and the slowdown still follows the count (S10.1.6.3) | part 1, `7ee1789` |
| K17 | Med | Reactivation still answers `bad-credentials`, `account-active` or `asked-recently` by the account's state, outside the sign-in guard (`auth/users.py:615`); re-authentication uses the throttle, not the guard (`ui/session.py:380`); sign-up returns before hashing when the address is taken (`auth/signup.py:95-103`) (S13.7.5.1) | part 1, `7ee1789` |
| K19 | Med | No engine sets `hide_parameters` (`store/db.py:47`); refusals aren't logged with their error id (`errors.py:89`); a read error's `detail` can hold a host path (`ui/receipts.py:504`); a peer's `message` is copied into `lastError` and its alert (`links/client.py:107`) (S13.7.8–9) | part 1, `7ee1789` |
| K12 | Med | `moneykata-connector connect` files the credentials at once, under whatever host the settings name, without showing it for the admin to confirm (connector `main.py:175-186`; S18.7.2). The host in the sealed box is checked (connector `core.py:331`) | part 3, `42a225b` |
| P6 | Med | A shared budget's recurring rows still carry the `accountId` and `accountName` of the owner's accounts the viewer can't see, and cross to linked servers (`ui/budgets.py:423`, `links/serve.py:158`); S11.3.1 says *an account not shared*. Gifts are done | part 4, `ce12371` |
| K22 | Low-Med | `own()` opens a write transaction and decrypts the link key on every `/link` call, `hello` included, before any signature check (`links/routes.py:36`); an unknown key is rate-limited but not refused before its body is read | part 4, `ce12371` (see 12.5) |
| K23 | Low-Med | Remove copy asks for the password only, not the phrase too (S16.13, S13.7.2); Settings › Network and its guide don't say the proxy is what limits the locked screen (S16.14, A14). The S11.9.10 point is done | part 5, `d678e48` |
| K25 | Low | Four points not done, two half done: the linked copy's key lives on as a hex string in the connection factory, and nothing refuses a connection after release; uploads aren't spooled in memory and the server doesn't refuse to start without a `/tmp` tmpfs (S13.7.6); applying a link change doesn't refuse a sequence at or below the last applied (`links/changes.py:149-207`, S11.9.5.3); `verify-backup` doesn't show or compare the manifest's `made`; the alert event still carries titles; dev mode is in the image and doesn't refuse outside a checkout (`main.py:53`) | parts 4 and 5, `ce12371`, `d678e48` |
| A26 | — | An expiry still takes a close from up to four days before the expiry date (`options/__init__.py:227`); S3.6 says the expiry day's close only, and asks without it | part 6, `6847ba9` |
| N11 | Med | Settings › Linked servers shows the last exchange and the shares coming in, not "what flows each way" (S11.7; `web/ui/components/links.js:140, 271`): nothing lists what this server sends | part 4, `ce12371` |
| N16 | Low | The OpenAPI document's problem codes leave out what the error handlers send (`invalid-request`, `method-not-allowed`, `http-error`, `server-error`, the `invalid-*` field codes, `errors.py:100-122`), and 265 operations still document their 422 as FastAPI's `HTTPValidationError`, not problem+json (S13.8.3) | part 7, `c8fd790` |
| C3 | — | `prune_files` keeps a file while any receipt not yet pruned names it, deleted or not (`receipts/retention.py:324`); S14.10.5 says a deleted receipt doesn't count | part 5, `d678e48` |
| C5 | — | A restore still rewrites a before-restore folder's receipts (`store/copies.py:187-200`); S15.6.8 and `operations.md` §6.1 say the receipt files stay where they are | part 5, `d678e48` |
| C9 | — | Written emails are kept 25 hours (`mail.py:153`); S16.2 keeps an invitation's a week, as long as its link works | part 2, `ab9dc23` |
| C11 | — | Only `keys verify` counts as a check of the phrase (`alerts.py:415`, `ui/settings.py:613-617`); S15.6.5 says every unlock does too | part 5, `d678e48` |
| C17 | — | `link-protocol.md` §1.3 and §7 say every answer to a signed call is signed back, while §7's own table has `locked` as 503 unsigned; §7 still opens "HTTP 403 (or 426 for a protocol)"; "try later" is said for `locked`, not `limit` | part 4, `ce12371` |
| C18 | — | S11.9.7 still says removing a share hides the item "at once", against S11.4's "at its next exchange" (R3.4 and S11.4 agree) | part 4, `ce12371` |
| C31 | — | `money.py`'s docstring says amounts are strings in JSON, and the import results still send `str(...)` (`ui/imports.py:364-370, 620`); R1.9 says exact number literals | part 7, `c8fd790` |
| C33 | — | The link carries seven kinds (`links/serve.py:24`, no `person`), and `link-protocol.md` §4.4 names no person item; R1.8 says any of the eight shareable kinds | part 4, `ce12371` |
| C36 | — | Wallets are read from mempool.space by default before anyone saves Settings › Bitcoin (`settings.py:222-223`); S16.7 says no wallet is read until an admin saves it | part 7, `c8fd790` |
| C44 | — | Every row left out teaches a skip, those already in the account included (`ui/imports.py:1149`, `importers/statements.py:373`); S1.3.3.4 says those teach nothing | part 7, `c8fd790` |
| C45 | — | A statement value older than 90 days is marked stale but raises no alert (`prices/refresh.py`, `alerts.py`); S4.3 and S12.11.1.2 list the alert | part 7, `c8fd790` |
| C46 | — | A wash sale's replacement in an IRA or a Roth IRA still takes the disallowed loss into its basis (`ledger/lots.py:249`); S3.8.3 says the loss is lost for good there | part 6, `6847ba9` |
| C47 | — | An adjusted option's strike isn't rounded to the thousandth (`options/adjust.py:129`; S3.10.1) | part 6, `6847ba9` |
| B33 | Med | Loans still have no Reconcile tab (`ledger/types.py:115`), though S1.11 names them and S1.11.7.1 expects their statements; a loan's statement-overdue alert links to `/reconcile`, which lands on the Overview only by a fallback (`alerts.py:459`, `web/ui/screens/account.js:57`). Either loans get the tab, or S1.11 and the alert say Overview | part 7, `c8fd790` (see 12.5) |
| B21 | Med | A payoff plan's extra payments still add the full PMI after it has ended (`loans/payoff.py:126, 135, 162`) | part 6, `6847ba9` |
| B22 | Low | Two of its five parts are missing and one is done differently: a portfolio's 1Y, 3Y and 5Y returns drop a deleted account (`ui/portfolios.py:418-426` calls `figures.combine` without `with_deleted`, while the value series keeps it); a donation's term uses the lot's `acquiredOn`, not a replacement's `heldFrom` (`ui/giving.py:467`); TXF leaves the C, L and digital-asset rows out and tells the user to enter them from the CSV (`taxes/exports.py:10-15, 79-81`) | part 6, `6847ba9` (see 12.5) |
| B23 | Low | Three money columns are still decimal text, against S14.3: `BudgetLine.amount`, `EstimatedPayment.amount` and `QualifiedExpense.amount` (`store/tables/budgets.py:41`, `taxes.py:146`, `education.py:41`) | part 6, `6847ba9` |
| B41 | Low | A pull's Activity names no link, actor or subject (`links/receive.py:82-91`, `links/manage.py:546-556`), so with several links nobody can tell which server pulled (S11.8) | part 4, `ce12371` |
| Tests | — | Section 4 asks for a golden-file test with each fix of a figure (S17.5), and `test_golden.py` covers only a simple wash sale, a short-held written put and the digital-asset boxes. B1's test has one sale, not the review's two; B2 has no test of a loss deferred again; B3, B4, B15 and B39, B7's rerun and B37's wallet caps have none. B38's test reads the OpenAPI document, which gives every 201 a `Location`, so it can't fail; nothing checks that a guessed `Location` reads the record | part 8, `1563bd5`, but for B7's rerun (12.5) |

### 12.3 Open outside this review

1. **Q15**: the requirements' final approval, after which `initial-code` merges into `main`.
2. **G23**: real receipt fixtures for the reader, waiting on the household's receipts.
3. **`docs/test-plan.md`**, T1 to T13: what needs systems the build doesn't have. Two more
   things never ran for real: the reader's Landlock file sandbox (the build host's kernel is
   4.18, so only the path without it ran, which the new alert now reports), and the arm64
   image on arm64 hardware (only emulated).
4. **`docs/requirements/later.md`**, L1 to L9: after the first release.

### 12.4 For the next reviewer

1. Start with 12.2's table, built in milestone 9, and check each row against the code rather
   than its commit message.
2. Of those, the ones that touch secrets and sign-in first: C23, K16, K15 with A12, K17, K19,
   K4, K12 and K25.
3. Then read what milestones 8 and 9 built, which no review has read yet: the host commands over the
   socket (K1, K6), TLS pinning and sealed link changes (K3, B24, B25, B26), the reader's
   sandbox (K4), the re-encryption journal and restores (K5, K9), categorisation rules (N1),
   corporate actions (N4), and closed years with amended returns (N5, S2.8, S8.15).
4. `web/check` runs every automated check (about 18 minutes); the connector's tests run in a
   pytest session of their own.

### 12.5 Decided while building milestone 9, for review

Where a row left a choice, milestone 9 took the one below and wrote it into the requirements;
each can be turned another way.

1. **B33**: a loan keeps no *Reconcile* tab: it is checked on its Overview against the balance
   its servicer reports (S1.9.4), S1.11 says so, and its overdue-statement alert leads there.
2. **B22, TXF**: TXF (V042) carries boxes A to F and the wash-sale adjustment only; a row with
   another code (C, L) or in a digital asset's box (G to L) is left out of it and said so, and
   S8.2 now states it, rather than writing codes the format has no field for.
3. **K22**: a call from a key with no link here is still read when its body is 1 MB or less,
   so its `not-linked` can be signed to the call and a peer that lost its link learns it
   (S11.6); a larger one is refused on its headers, unsigned (`link-protocol.md` §7).
4. **B38**: a 201's `Location` is the record's own path where the API has a route that reads
   it, otherwise the list that holds it (S13.8.4); budgets, people and transactions gained
   read routes.
5. **C36**: dev mode's stub source reads wallets whether or not Settings › Bitcoin was saved.
6. **C33**: a linked server's user sees a person here only through a share of them or of a
   gift plan for them; the linked window's Gifts lists people shared on their own.
7. **C9**: an email carries how long its link works, a day unless it says otherwise and an
   invitation's a week, and its written file or queued row lasts that long.
8. **B7**: the rerun of wash sales when an account's lot method changes still has no test of
   its own; the method recorded on each sale is tested.
