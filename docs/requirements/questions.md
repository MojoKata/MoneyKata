# Open questions

Questions that wait on a decision. Each has a lasting id (Q1, Q2, …), shared with the questions
asked while MoolaKata is built: a question that is answered is removed, its answer goes into
the section it belongs to, and its id is never used again. A new question takes the next
number. Q1–Q29 are answered. Each carries a rank: **High** decides what the next change is,
**Med** decides something before the first release, **Low** can wait. The
[README](README.md#open-questions) lists them.

## Q30: How the connector stores its secrets — Low

**The question:** whether the connector's vault stays one sealed file (S18.3.1), or moves into
an encrypted database, as MoolaKata's own data is kept in SQLCipher (S14).

**What it is:** `vault.json` holds every Connection's credentials with the host each is bound
to, the sealing key's private half, and a Schwab Connection's app secret and tokens. The whole
file is sealed with AES-256-GCM under a key that HKDF-SHA256 derives from the 12 words, and
sealed again with a fresh nonce at each change. The words are never stored, so the connector
starts locked (S18.3.2).

**The options:**

1. **Keep the sealed file.** The connector's image carries no database engine, and the file is
   small enough to read whole; sealing all of it at each change costs little at a household's
   few dozen entries.
2. **SQLCipher, as MoolaKata.** One engine in both services, and a change writes only its own
   rows. The connector gains the `sqlcipher3` wheel, a schema and its migrations, with the key
   from the words as SQLCipher's raw key.

**Follows the answer:** the connector's description on Docker Hub, which says how its
credentials are stored.
