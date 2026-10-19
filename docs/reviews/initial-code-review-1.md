# Review 1: the requirements, with secret handling in focus

**Scope.** Every file under `docs/requirements/` (README, S1–S18, gaps, questions, later,
out-of-scope, rejected ideas), read whole; `docs/schema.md`, `docs/link-protocol.md`,
`docs/connector-protocol.md` and `docs/operations.md` where the requirements lean on them;
and, to check what the requirements claim against what was built, a reading of
`web/server/src/moolakata/keys/`, `store/maintenance.py`, `store/repos/secrets.py`,
`auth/twostep.py`, `links/copy.py` and `connector/moolakata_connector/{keys,vault}.py`.

**Ranks** follow `gaps.md`: **High** blocks the first release, **Med** is needed before it,
**Low** can follow it. Nothing here has been written into the requirements, `gaps.md` or
`rejected-ideas.md`; candidate gaps carry no G id until they are recorded there. Each finding
names the items it touches so the fix can be placed.

## 1. Summary

The requirements are unusually complete and internally careful: ids are stable, the threat
model is stated in most places (S15.3.7, S11.9.10, S18.2.4), and the implementation of the key
hierarchy matches S15 closely. The problems are concentrated where two components meet, and
where a section states a protection that the surrounding design does not deliver.

| Id | Rank | Finding |
|---|---|---|
| F1 | High | A leaked master key or phrase is handled as a key problem (rotate); it is a data problem (every copy ever made is open), and the text points admins the wrong way |
| F2 | High | The connector's identity and sealing keys sit unencrypted beside the vault, so "a stolen disk yields nothing" (S18.2.4) is false: it yields impersonation and every credential entered afterwards |
| F3 | High | A compromised MoolaKata can steer the connector: Connection `settings` (`url`, `path`, `rules`) come from MoolaKata, so it can redirect OFX credentials to any host and read files off the connector's volume. S18.2.4 says it "gets no credential" |
| F4 | Med | The per-secret layer protects against a threat that does not exist in this design; S14.4 and S15.3.3 disagree on what wraps what; the lists of secrets disagree; the link key contradicts "decrypted only when used" |
| F5 | Med | The default admin starts with a published password on a network-reachable port, with no setup token |
| F6 | Med | Until SMTP is set, invitation and reset links sit as plain files in the data directory; S15.1 does not list the mail folder, and nothing says how an admin reads them |
| F7 | Med | A pairing is live before anyone compared fingerprints, so a credential can be sealed to whoever answered the code first |
| F8 | Med | Re-authentication (S13.7.2) is missing for Re-encrypt, for entering a Connection's credentials and for every secret-bearing Settings field |
| F9 | Med | Re-encryption interacts badly with backups, `pre-upgrade/`, `before-restore-*/`, rotation and restore; none of it is specified |
| F10 | Med | The `tls` listener's private key and the uploaded certificate key (S13.3, S16.15) have no stated storage and are the one secret that may sit plain in the data directory |
| C1 | Med | S9.8.5 says OCR text never crosses a link; S11.5.1 and the link protocol send it |
| F11 | Low–Med | How a receipt's plaintext reaches the reader worker (S9.8.4) is unstated; S11.9.6.5 promises "never touches the disk" for linked receipts only |
| — | Low | A dozen wording conflicts and small gaps, section 4 and 5 |

## 2. Secret handling: flaws

### F1 (High): a leaked master key is a data leak, and the text says otherwise

**What the requirements say.** S15.8.1.2 lists "a lost recovery sheet, a compromised
password-manager vault, a disk with the key file sold, recycled or lost" as reasons to
**rotate the master key**. S15.7.1 rotation re-wraps the data key and nothing else, keeps the
previous key "until every backup made before the rotation has been pruned", and "Settings
names the date after which the previous key is no longer needed". S15.7.2 re-encryption is
"rarely needed: only when the data key may have been exposed, such as a memory dump".
S15.6.7 says backups "can go to a NAS or a cloud bucket as they are". S15.7.3.2 admits, in one
line, that rotation "does not protect copies made before it".

**The problem.** Whoever holds the old phrase and *any* copy of the data directory or any
backup made before the rotation has the data key, and with it the whole database, every
receipt and every secret, for ever. A lost recovery sheet is therefore not a reason to rotate;
it is the case S15.7.2 calls "the data key may have been exposed", and even re-encrypting
only protects copies made *after* it. Three consequences the text gets wrong or leaves out:

1. **"The date after which the previous key is no longer needed"** is computed from
   MoolaKata's own backup pruning (S14.6). A NAS snapshot, a cloud bucket with versioning,
   a Proxmox or TrueNAS replication (operations §2.1–2.2) and any copy made by hand keep
   backups that MoolaKata never prunes. The date is wrong for every household that followed
   S15.6.7's advice, and destroying the previous key on that date can also strand their own
   off-site backups.
2. **The only remedy for a leaked phrase is**: revoke secrets at source (S15.8.3), re-encrypt
   (new data key), rotate the master key (new phrase), and then **delete every backup made
   before**, everywhere it was copied, or accept that those copies are readable by the
   finder. The requirements never say the last step, and S15.8.3 says "rotation alone leaves
   every secret readable from any old copy" as if only the secrets were at stake.
3. **A memory dump exposes the master key too**, not just the data key: the running server
   reads the key file at start (S15.4) and again for Re-encrypt (`maintenance.reencrypt`
   re-reads it). S15.7.2's "only the data key" framing is not safe.

**Done.** S15 opens with a terms table and a diagram of the key levels; S15.7.1.4, S15.7.2,
S15.7.3 (with a timeline of what each step closes) and S15.8 are rewritten around copies;
S16.13, Settings › Key storage, its guide, the mockup, operations §7.1 and rejected idea 17
follow.

**Done, further** (parts 1 and 2): the master key is the phrase alone, never stored, entered
after every start; backups are the database with its keyring; every copy carries its keyring
and is re-wrapped, rewritten, left or deleted at rotation and re-encryption; the copies on the
host are listed in Settings with how each opens.

**Suggested change.** Rewrite S15.7.3 and S15.8 around what a copy of the data reveals rather
than around keys: (a) a leaked key or phrase means every prior copy is open, (b) the
response is revoke, re-encrypt, rotate, purge old copies, in that order, (c) the previous
key's "can go" date is only true for copies inside the backup directory, which Settings
should say, (d) a memory dump or debugging session calls for rotation as well as
re-encryption. Record the trade-off (no per-backup key, so no way to lock old copies) in
`rejected-ideas.md` so it is not re-raised.

### F2 (High): the connector's keys outside the vault contradict its threat model

**What the requirements say.** S18.4.5: "The identity key sits beside the vault, not in it,
so a locked connector can still report." `connector-protocol.md` §2.1: both the identity key
(Ed25519) and the **sealing key** (X25519) are "kept beside its vault, not in it".
`keys.py` saves both private keys base64 in a plain file. S18.2.4 then claims: "a stolen
disk, backup or powered-off machine yields nothing, since the vault opens only with the
words", and "a compromised connector … can read nothing from MoolaKata".

**The problem.** A copy of the connector's volume gives the thief:

- the **identity key**: they are now the paired connector to MoolaKata. Every report
  answer hands them every live Connection's `settings` (OFX `url`, `accountId`, `bankId`
  routing numbers, Schwab `appKey`), owner names, labels, account ids, institution-account
  names with last four digits, and they can post files into every synced account;
- the **sealing key**: every credential sealed in the browser from then on (S18.7.1) is
  collected in a report answer and opens with it. The owner typing their Schwab password
  into MoolaKata has no way to know a clone is collecting it.

Only the credentials already in the vault stay closed. "Yields nothing" and "can read
nothing" are both false, and the gap is exploitable from a lost laptop (S18.1 invites running
the connector on one).

**Done.** The sealing key's private half is made at pairing and filed in the vault (`pair`
needs the vault unlocked); `pairing.json` holds only the public half; MoolaKata hands a sealed
box only to a connector reporting unlocked; S18.2.4 states what each thing taken yields;
operations §8.13 says to Unpair a lost host.

**Suggested change.** Keep the identity key outside (a locked connector must report), but
**put the sealing key in the vault**: a locked connector cannot use a credential anyway, so
it has no need to open a box. State plainly what the identity key alone yields (impersonation
until Unpair, settings and account labels), tell admins to **Unpair when a connector host is
lost**, and have MoolaKata alert when a report arrives from a new client address or with a
new `MK-Conn-Version` after a silence, since nothing else distinguishes a clone. Consider
letting MoolaKata hold the sealed box only while the connector reports *unlocked*.

### F3 (High): MoolaKata controls where the connector sends credentials and what it reads

**What the requirements say.** `connector-protocol.md` §4.2: the report's answer carries each
Connection's `settings`; §6: `ofx-direct`'s settings include `url`, and "a driver's host is
the one it declares, or, for OFX Direct Connect, **the server its owner named in the
settings**"; the Folder driver's `path` and `rules` likewise. S18.2.4: "A compromised
MoolaKata gets no credential, and can't reach or command the connector."

**The problem.** Settings are commands. A compromised MoolaKata (or an admin with a Share
write on the owner's settings, if ever allowed) changes a Connection's `url` to a host it
controls, and the connector's next run sends the stored OFX username and password there,
inside the allowlist, because the allowlist is derived from the same settings. For the
Folder driver it sets `path` to the connector's own volume and `rules` to `* → <any
account>`: the connector then posts its vault file and its **plain keys file** (F2) to
MoolaKata as "statements". `file-refused` does not help when the receiver is the attacker.

**Done.** A credential is filed with the host its Connection's settings name (S18.7.3); a
changed host sends nothing, drops the credential and reports *needs a sign-in*; the Folder
driver is rooted at the watched folder mounted at `/watch`, and MoolaKata refuses a path that
reaches outside it at the form.

**Suggested change.** The connector must **bind a credential to its destination when the
credential is filed**: the OFX `url` (host) is stored in the vault entry next to the
password, and a later change from MoolaKata is refused until the owner re-enters the
credentials, with the Connection reported as *needs a sign-in: the server address changed*.
The Folder driver's root is **fixed on the connector's host** (the mount point in
`compose.yaml`), and `path` from MoolaKata is relative to it, with `..` refused. Rewrite
S18.2.4 to say what a compromised MoolaKata can still do: alter the code that seals (already
admitted in S18.7.1), and steer drivers within what they are pinned to.

### F4 (Med): the per-secret layer's rationale, and three disagreements about it

1. **Who it protects against.** S15.3.6 says the associated data "stops anyone with write
   access to the database from moving one user's API key onto a record they control", and
   S15.3.4 that secrets are encrypted on their own "so that a database opened for
   maintenance (S14.7) still shows no secret". But the database key and the secrets key are
   both HKDF outputs of the one data key (S15.3.2, `master.DataKeys.derive`). Nobody can
   hold write access to the SQLCipher database without holding the material that opens
   every secret; `db shell` shows no plaintext only because the shell does not run the
   unwrap. The per-secret data key adds a wrap under the same secrets key with the same
   associated data, which buys nothing over sealing directly under the secrets key. The
   layer is still worth keeping as hygiene (a mistake in one query cannot print a key;
   `rewrap` makes re-encryption cheap), but S15.3.4 and S15.3.6 should say that, not claim
   a boundary. Also "one user's API key": price-source keys, SMTP and node credentials are
   server-wide; the only per-user secrets are two-step seeds.
2. **What wraps what.** S14.4: each secret's data key is "wrapped under a key derived from
   the **master** key". S15.3.3: wrapped under the **secrets key**, which comes from the
   data key. The code does the latter. Fix S14.4.
3. **Which things are secrets.** S14.4: price-source keys, node credentials, SMTP password,
   link private keys, two-step seeds. S15.1.3 omits the two-step seeds. S15.3.4's uses ("a
   price refresh, a bitcoin wallet read, an email") omit link signing and two-step checks.
   Missing from every list: the pending two-step seed (built, `twostep.PENDING_SEED`), the
   Electrum certificate fingerprint (S1.6.2.4; integrity-critical, not secret, which is worth
   saying since it sits in the encrypted database), the sealed credential box waiting for
   the connector (S18.7.1; where it is stored, and that it is deleted on Unpair or Remove,
   not only after `credential/taken`), and the TLS key (F10).
4. **"Decrypted only when used … for that one call" (S15.3.4)** is not true of the link key,
   which signs every `/link` answer, every `/connector` answer and every exchange, so it is
   decrypted continuously. Either say so (it is held for the server's lifetime like the
   data keys) or keep the per-call model and say the cost is accepted.

**Decided:** kept as it is; the password is changed at the first sign-in, moments after install.

### F5 (Med): the default admin's published password

S10.1.2: "A server with no users creates `admin` with a published default password at start."
S16.14 allows any address to reach `/ui` by default. Between the first start and the admin's
first sign-in, anyone who can reach the port claims the server, and the setup step then gives
them the admin's email. On a LAN this is a race; behind a proxy that an admin exposed too
early it is a takeover. Standard fix: print a **one-time setup code** in the log at first
start (as the refused-start line is read, operations §5.1) and require it on the setup
screen, or accept sign-in only from loopback until setup is done. Record in S10.1.2 and
operations §2.4.

**Done:** Settings › Email lists the written emails and opens one after the password again;
each file is removed a day after it was written; S15.1.7 and S16.2 say the folder is plain.

### F6 (Med): the mail folder holds live tokens in plain text

S16.2: "Until a host is set, emails are written to the mail folder in the data directory."
Those emails carry invitation, reset, email-change and sign-up links, each a bearer token
good for 24 hours (S10.1). The folder is in the data directory but not listed in S15.1.7
("not encrypted: the configuration file, the logs, and the key file"), not in the backup set
(S14.6), and nothing in S16.2 or operations says how an admin reads the files to pass a link
on. Milestone 1 ships exactly this mode ("email written to a folder until SMTP is set",
S17.9.1.4). Say in S15.1.7 that the mail folder is plain, make the written emails readable
from Settings › Email (the queue it already shows) rather than from the host, and expire the
files with their tokens.

**Done:** a pairing is confirmed by an admin in Settings › Connector; until then no sealed
credential is handed over, no file is taken and no sign-in can be sealed (S18.4.2).

### F7 (Med): a pairing is live before fingerprints are compared

S18.4.2 and `connector-protocol.md` §4.1.3: both sides show the connector's fingerprint "for
the admin to compare; a mismatch means someone else answered the code first, and the admin
unpairs". But pairing takes effect at once, and S18.7.1's credential dialog is used by an
account's owner, who is usually not the admin and has no reason to compare anything. A
pairing code is a 24-hour bearer secret in a URL-like string that gets pasted into chats
(S15.6.4 warns of this for the phrase, not for codes). Add a **confirmed** state: the
pairing exists but no credential can be sealed to it and no file is accepted from it until
an admin confirms the fingerprint in Settings › Connector. The same applies, more mildly, to
a link's approval (S11.1.2), which already has that step.

**Done:** S13.7.2 and the routes now ask for the password again for every secret-bearing
setting, the sealed credentials, Network, the Admins group, Re-encrypt and the rest.

### F8 (Med): the re-authentication list is incomplete

S13.7.2 lists the password, email, two-step, access tokens, linked-copy keys and reset,
sharing with a link, pairing and unpairing, pruning and export. Missing: **Re-encrypt**
(S15.7.2, an admin button that rewrites every file), **entering or changing a Connection's
credentials** (S18.7.1: the one place a bank password is typed), and every Settings field that
stores a secret: the SMTP password (S16.2), the node's RPC password (S16.7), a price source's
key (S16.6), and the TLS key (S16.15). Also changing Settings › Network (S16.14), which widens
who can reach the app, and making a user an admin (S10.1.8).

**Done** (part 2): a verified backup first, backups and re-encryption exclude each other,
pre-upgrade copies carry their keyring, rotation and unlock refuse a pending re-encryption
under another phrase by name, and the finish-at-next-unlock behaviour is written down.

### F9 (Med): re-encryption against backups, restores and rotation

S15.7.2 re-encrypts "a few at a time while the server keeps serving". The requirements do not
say what happens when:

- the **daily backup** runs mid-way: it copies one `keyring` and a receipts directory that
  is half under each key, so the backup cannot be fully restored (the code writes the new
  ring to `keyring.next`, which is neither backed up nor in the restore set `RESTORED`);
- **`pre-upgrade/`** copies (S14.1.3) and **`before-restore-*/`** folders (S15.6.8) were made
  under the old data key: after re-encryption the old keyring is gone and they are
  silently unopenable, though S14.1.3 presents them as the way back from a bad upgrade;
- **`keys rotate`** runs while `keyring.next` exists: it re-wraps `keyring` only, so the
  pending re-encryption can never finish under the new master key;
- the server **crashes** mid-way: the code finishes at next start, which S15.7.2 should say,
  together with "no backup runs while a re-encryption is in progress" and "pre-upgrade and
  before-restore copies made before it no longer open".

**Decided and written:** a plain file in the data directory, mode 0600, which protects the
listener and not the data (S13.3, S15.1.7, S16.15).

### F10 (Med): where the TLS private key lives

S13.3: in `tls` mode the self-signed certificate is kept "in the data directory". S16.15:
Settings › TLS holds "the listener's certificate and key". Neither says whether the private
key is a plain file in the data directory (then it is the one secret R1.13's "everything the
server stores is encrypted at rest" misses, and `tls` mode is the one users on a LAN are
told to use) or a sealed secret in the database (then the listener must read it before the
database is open, which the start order must allow). Decide and write it into S13.3 and
S15.1.

**Done:** S9.8.4.2 says the file reaches the worker over a pipe, which is what the code does.

### F11 (Low–Med): receipt plaintext and the reader worker

S9.8.4.2 runs OCR "in a separate worker process", restarted after a crash or a timeout. The
requirements never say how the decrypted receipt reaches it. S11.9.6.5 promises "plaintext
never touches the disk" for a *linked* receipt only. State that own receipts are passed to
the worker over a pipe or shared memory, never a temporary file, and that a killed worker
leaves nothing behind; or, if a temporary file is unavoidable for pypdfium2, that it is in a
private tmpfs and wiped.

**Done:** 1 is moot (no phrase command exists; host commands queue for Activity), 2 and 4 are
moot (no config entry, no key file), 3 is written into S13.7.9, 5 lengthens the codes, 6 is in
S15.6.2, 7 and 9 are reworded, 8 signs manifests, 10 locks the address.

### F12 (Low): smaller secret-handling points

1. **`keys phrase` is not recorded.** S15.6.5 records every `keys verify`; S15.7.4 records
   rotation. Showing the phrase again (S15.6.1), and writing it to `--file`, is the more
   sensitive act and is recorded nowhere. Record it in Activity, and tell the admin to
   delete the sheet file after printing.
2. **S15.4.6 "to record the previous key in it"** reads as key material in `moolakata.toml`,
   which operations §1 calls "never a secret". The code records a path and a fingerprint.
   Say "to record the previous key's file and fingerprint".
3. **The SQLCipher key travels inside SQL text** (`PRAGMA key = "x'…'"`, `PRAGMA rekey`).
   S13.7.9 forbids secrets in logs; add that statement logging (SQLAlchemy `echo`, slow-query
   logs) is never turned on, or the key is in the log.
4. **S15.4.5 "A Docker secret works in place of the mounted directory"** is unverified: a
   compose file secret is a bind mount with mode 0444, which S15.4.4's "can be read by
   anyone but its account" check refuses. Verify or drop the sentence.
5. **Recovery codes** (S10.1.6.2) are ten short codes hashed with SHA-256 (S15.1.6 says SHA-256
   is for "a random value"). State their alphabet and length (at least 64 bits) or hash them
   with argon2id, since a short code hashed plainly is brute-forceable offline.
6. **The password manager is a single point.** S15.6.2.2 (master phrase), S11.9.2.1 (every
   linked copy's words) and S18.3.1 (the connector's words) all go to "the household's
   password manager". One breached vault opens the server, every linked copy and every bank
   sign-in. S15.6 should say the master phrase gets a vault of its own, or an offline copy
   as the primary.
7. **S11.9.3.1 "Nothing about it reaches the browser"** is backwards: the words are typed in
   the browser and sent to the server. Say "nothing about the key is sent back".
8. **Backup manifests are unauthenticated.** `manifest.json` (operations §4) carries hashes
   anyone can rewrite; `verify-backup` cannot tell a backup swapped for an older encrypted one.
   An HMAC under a key derived from the data key would close it cheaply.
9. **S11.1.3 "No shared secret ever crosses"** is not quite true: the link code's one-time
   secret crosses once in `join`, over TLS the joiner may not be able to verify (self-signed).
   The design is still sound because the fingerprint is compared out of band; say that
   instead.
10. **S13.7.5.1 locks the username** after ten failures, so anyone can lock the admin out
    for 15 minutes at will. Usual answer: lock the address, and slow (not lock) the username.
    **Done.**

## 3. Conflicts between sections

**Done:** every row below is resolved in the sections named, except that C14 is resolved by
queuing host commands for Activity with no "who", which S15.4.7 says.

| Id | Where | Conflict |
|---|---|---|
| C1 | S9.8.5 vs S11.5.1, `link-protocol.md` §4.4 | S9.8.5: the text read from a receipt "never cross[es] a link". S11.5.1: with Include receipts, receipts "travel with … the text read from them, so the receiving side never runs OCR". The protocol's `files` carry "what was read from them". S11 is the intended behaviour; fix S9.8.5. |
| C2 | S14.4 vs S15.3.3 | Secrets' data keys wrapped under "a key derived from the master key" vs under the secrets key from the data key (F4.2). |
| C3 | S15.1.3 vs S14.4 | Two-step seeds are secrets in one list and absent from the other (F4.3). |
| C4 | S18.2.4 vs S18.4.5, `connector-protocol.md` §2.1 | "A stolen disk yields nothing" vs private keys kept plain beside the vault (F2). |
| C5 | S18.2.4 vs `connector-protocol.md` §4.2, §6 | "A compromised MoolaKata gets no credential, and can't … command the connector" vs settings, including the OFX host and the folder path, sent by MoolaKata (F3). |
| C6 | S18.2.4 vs `connector-protocol.md` §4.2 | "A compromised connector … can read nothing from MoolaKata" vs the report answer carrying every Connection's settings, labels, owner names and account last-fours. |
| C7 | R1.13 vs S15.1.7, S16.2, S13.3 | "Everything the server stores is encrypted at rest" vs the mail folder (F6) and the TLS key (F10), neither listed among the exceptions. |
| C8 | S15.3.4 vs `link-protocol.md` §2.1 | "Decrypted only when used, for that one call" vs the link key signing every call and answer (F4.4). |
| C9 | S15.7.2 vs S15.8.1.2 | Re-encryption "rarely needed, only when the data key may have been exposed" vs a lost sheet or key file, which exposes the data key through any copy (F1). |
| C10 | `schema.md` §2.5 vs S11.9.1 | "Anything visible on disk … never an ID" vs `links/<link-id>/`, a UUIDv7 that dates the link. Name the folder by a random id kept on the `Link` row. |
| C11 | S13.7.2 vs S15.7.2, S18.7.1, S16 | The re-authentication list vs the actions that most need it (F8). |
| C12 | R3.1 vs S13.5 | "The only outbound calls are to price sources, the bitcoin explorer or node, and linked servers" omits the SMTP server, which S13.5 includes. |
| C13 | S11.9.1 vs `link-protocol.md` §4.4 | The main database holds the shared items' "ids, kinds, owner's display name and the people they name (not their names or values)"; the protocol's `items` carry `name`, and §4.4.4 lists what the receiver keeps in the main database without saying `name` goes only into the sealed copy. Say it. |
| C14 | S15.6.5 vs `keys verify` | Settings records "who" confirmed the phrase, but `keys verify` runs in a one-off container with no signed-in user. Say what "who" is (the host account, or a name typed). |

## 4. Candidate gaps (not yet in `gaps.md`)

**Done:** 1 to 8 by parts 1 to 3; 9 (clocks) in S11.1.3, the protocols and operations; 10 rejected;
11 in S9.8.4; 12 as later work L3; 13 in S16.14; 14 by the notice to the old address and the
notice of a sign-in from a new address (sessions and users keep the addresses seen); 15 by the
host events; 16 moot. The connector's new-address alert of F2 is built as well (S18.5.4).

Each would take the next free G id when recorded. Ranked as `gaps.md` ranks.

1. **(High) Response to a leaked master key or phrase**, including off-site backups: F1.
2. **(High) The connector's key storage and what a stolen connector yields**: F2.
3. **(High) Pinning a Connection's destination and the Folder driver's root on the
   connector**: F3.
4. **(Med) First-start bootstrap of the admin account**: F5.
5. **(Med) The mail folder**: its encryption, how an admin reads it, token expiry: F6.
6. **(Med) Pairing confirmation before use**: F7.
7. **(Med) Re-encryption's interplay with backups, old copies, rotation and crashes**: F9.
8. **(Med) The TLS private key's storage and the start order it needs**: F10.
9. **(Med) Clock discipline.** Signed calls refuse a 60-second skew (S11.1.3,
   `connector-protocol.md` §3.2) and TOTP allows one 30-second step (S10.1.6.1). Nothing
   tells operators that the hosts, the connector's laptop included, need NTP, and nothing
   alerts when a peer or the connector is refused for `clock-skew` rather than for being down.
10. **(Med) The connector after a reboot.** **Decided:** rejected (rejected idea 19); a restart
    needs a person, for the server as well. S18.3.2 locks it at every start and S18.5.1
    alerts admins; with Schwab's weekly sign-in (S18.9.3) an unattended household loses sync
    silently after a power cut until someone types the words. Decide whether an opt-in
    auto-unlock from a host-held file (with the weaker threat model stated) is offered, and
    record the decision either in S18.3 or in `rejected-ideas.md`.
11. **(Low–Med) How receipt plaintext reaches the OCR worker**: F11.
12. **(Low) Treasury data.** S4.3 prices Treasuries, I bonds and EE bonds "from the Treasury's
    published yield curve and savings-bond rates", but no `TickerSource` is named, the egress
    guard's list (S13.5) does not include a Treasury host, and S16.11 does not ship the
    figures. Say whether they are fetched (then from where, and guarded) or shipped.
13. **(Low) Settings › Network's default of "the LAN and the overlay"** (S16.14) for
    `/connector` is undefined behind a reverse proxy, where the client address is whatever
    the trusted proxy forwards. Define the default as explicit ranges (RFC 1918, 100.64/10
    for Tailscale, fc00::/7) and show them.
14. **(Low) Account-security emails.** S10.1.9 sends "password changed" and "two-step
    turned on or off" but not "email address changed" to the *old* address, nor a sign-in
    from a new browser. Both are cheap and the usual defence against a quiet takeover.
15. **(Low) `db shell` and `keys phrase` leave no trace** (S14.7, S15.6.1); Activity records
    every admin action in the UI but nothing done on the host. At least log them at the next
    start from a marker file.
16. **(Low) Docker secrets as the key source** (S15.4.5): verify or drop (F12.4).

## 5. Observations that need no change, recorded so they are not re-raised

- **The key hierarchy as built matches S15.3**: 16-byte master, HKDF with the labels
  `moolakata master`, `moolakata database`, `moolakata receipts`, `moolakata secrets`,
  keyring with AAD naming the master key id, per-secret AES-GCM with AAD
  `record type ␟ id ␟ field`, `PRAGMA rekey` and file re-wrapping for Re-encrypt.
- **Nonce use is safe**: one message per secret data key, random 96-bit nonces for the
  small number of wraps under the secrets key, a fresh X25519 key per file.
- **The linked copy's verifier** (the X25519 public key derived from the copy key) is a
  sound way to check the words without storing anything that derives them.
- **The copy key has no recovery phrase by design** (S11.9.8); Reset copy is the right
  answer.
- **Rejected idea 1** (a separate keys process) and **2** (external KMS) are rightly
  rejected for a household server, and S15.3.7 says honestly what root gets.
- **Cross-protocol domain separation** between link and connector signatures
  (`MK-LINK-1` vs `MK-CONN-1`, and the `-ANSWER` prefixes) is correct even though one link
  key signs both.
- **The 128-bit master key** gives 128-bit security for AES-256-GCM; that is enough here and
  the twelve words are the right trade.

## 6. Suggested order

1. F1, F2, F3 and C1 to C9: these change what admins are told and what the connector
   stores, and they are the ones a reader of S15 and S18 would be misled by.
2. F5, F6, F7, F8: each is a small change to a screen or a list, and each touches the
   mockup (CLAUDE.md: the mockup moves with the requirement).
3. F9, F10, F11 and the Med candidate gaps: specify, then record what stays open.
4. The Low items in one sweep, with `rejected-ideas.md` taking the decisions that turn
   something down (the connector's auto-unlock, a per-backup key).
