# S14. Storage and secrets

1. **One SQLite database** (WAL) under the data directory, through SQLAlchemy, for everything
   but what links bring in, which lives in a SQLCipher database per link (S11.9). The schema
   follows [`schema.md`](schema.md), which a test enforces. The database is encrypted with
   **SQLCipher** under a key derived from the data key (S15.3), through the same
   `sqlcipher3` engine as linked copies.
   1. **Tables** are declared with SQLAlchemy Core (`Table`, `Column`) in `store/tables/`,
      one module per area, on one `MetaData`. A table module holds only columns, keys,
      constraints and indexes.
   2. **Entities** are plain dataclasses in `store/entities/` that import nothing from
      SQLAlchemy. `store/mapping.py` maps each one onto its table
      (`registry.map_imperatively`), relationships included. Business logic lives in the
      feature modules (`ledger/`, `loans/`, `giving/` and the others), and a test fails when
      their calculation code imports SQLAlchemy.
   3. **Revisions:** each change to the tables is a numbered Alembic revision, generated,
      reviewed by hand and committed, and a test fails when tables and revisions disagree.
      At start the server copies the database (verified) into `pre-upgrade/` in the data
      directory, keeping the three newest copies, and then migrates it, one revision per
      transaction. A committed revision is never changed: a change is a new revision.
      Until the first release, the revisions may be folded into one baseline, keeping at least
      one revision after it so a test can carry rows written at the baseline through the
      server's own upgrade.
   4. **Access:** each table has a repository module. A unit of work is `Database.tx()`
      (`BEGIN IMMEDIATE`) or `Database.read()` (`PRAGMA query_only`, which refuses any
      write). Foreign keys are on, with a 10-second busy timeout.
   5. **Soft deletes**: records are never removed. Deleting one sets its `deletedAt` and
      `deletedById` (its `deleted` is generated from `deletedAt`), and each table's view works out whether a record is
      deleted through the records it belongs to. [`schema.md`](schema.md) (S1) sets the
      fields, the views and the few exceptions.
2. **Receipts** are files beside it (S9.2), owned by the server's account, mode 0600 in a
   0700 directory.
3. **Decimals**: money is stored as **integer cents**, and quantities and prices as **decimal text** validated to a fixed scale (18
   places, enough for wei), through a small SQLAlchemy column type. JSON carries both as exact
   numbers (S13.8.2). Python uses `decimal.Decimal` with a context of 34 digits and rounds
   `HALF_EVEN` except where a tax rule says otherwise. No amount passes through a float.
4. **Secrets** (price-source keys, the bitcoin node's credentials, the SMTP password, link
   private keys, two-step sign-in seeds) are encrypted each on its own with AES-256-GCM under a data
   key of their own, wrapped under a key derived from the master key, with associated data
   naming the record
   and field, so a ciphertext copied onto another record fails to decrypt (S15.3). Secrets are
   decrypted only when used, never logged, and never sent back to the browser: the UI shows
   a stored secret as *set*, with when and by whom. Passwords, two-step recovery codes, and session,
   reset and invitation tokens are stored as hashes.
5. **The master key**: 128 random bits in a file on the host, outside the data directory and
   its backups, never in the database, backed up as a 12-word recovery phrase. S15 covers how it is made, protected, backed up,
   restored and rotated.
6. **Backups**: daily and verified, of the database **and the receipts directory**, to a
   directory set on the host; the time of day and the number of copies kept are Settings. The
   server makes and verifies (`PRAGMA integrity_check`) the copies itself, and prunes the
   oldest beyond the number kept (**backup pruning**). `moneykata db backup` makes one at
   once, and `moneykata db verify-backup` checks one (the newest by default) without changing
   it: every file against the manifest's hashes, and that it opens with the master key or a
   previous one. They are
   encrypted as the data is, and open with the master key's recovery phrase (S15.6). A
   restore is documented, and tested by a check. Linked copies (`links/`) are left out: they
   can't be checked without their access keys, and they are pulled again from their sources
   after a restore (S11.9.9).
7. **Financial data at rest** is encrypted with the rest of the database (S15.1). Ordinary SQLite tools can't read it. `moneykata db shell` opens it,
   as root on the host, with the key from the key file.
8. **Export**: a user can export their own data (accounts, transactions, lots, receipts) as a
   ZIP of CSVs and files, at any time. This is the way out, and the backup a single user can
   keep.
9. **Times and dates.**
   1. **Every timestamp is stored in UTC** (`deletedAt`, a session's start, an alert's
      opening, a price's `as_of`), and shown in the viewer's time zone.
   2. **Each user's time zone** is set in Profile: **Auto**, the server's time zone (from
      the host, shown in Settings › General), or a zone they choose by name
      (`America/Denver`).
   3. **Calendar dates have no time zone**: a transaction's date, a statement's period, a
      birthday and a due date are dates as the institution or the user wrote them, never
      shifted.
   4. **A trading day** is the US market's, in New York time: a daily close is dated by its
      market day, whatever the viewer's zone (S4.4).
   5. **"Today" for a user** follows their time zone: the year a tax year screen opens on,
      when an occasion's lead time starts, and the hour their daily summary email goes out
      (S12.11.5).
10. **Retention and file pruning**: records are never removed: not records, soft-deleted
    records (`schema.md` §4) or Activity, so every figure can be looked back on as it was
    (R3.10). What can be removed, by hand, is the **files** of receipts and statements whose
    retention has run out: **file pruning**. Backups are pruned on their own, shorter
    schedule (S14.6), and price history is kept for ever (S4.6).
    1. **Retention periods**:
       1. **A category** has **Keep receipts for** a number of years, counted from when the
          record a receipt is attached to ended (`schema.md` §6). Empty, the default, keeps
          them for ever. A subcategory without its own takes its parent's. Any whole number
          of years from 1 is allowed; under 7 the field warns that 7 covers every IRS audit
          window.
       2. **Statements** have one period, in Settings › Storage (S16.17), empty (for ever)
          by default.
       3. **A file** (a receipt or a statement) has a **Keep** toggle that keeps it for ever.
    2. **When a file expires**: at the latest end of the records it is attached to, plus the
       longest of their periods. It never expires when Keep is on, when any of those records
       has no period (a transfer, an uncategorised transaction, a category kept for ever), or
       when it is attached to nothing. Expiry is worked out, never stored, so a changed
       period moves every date at once.
    3. **Shown on each file**: *Kept until Mar 2031*, in bold within 90 days of it;
       *Kept while the lot is open* while a record it is attached to hasn't ended; or
       *Kept for ever*. An expired file shows *Expired Mar 2031, prunable*.
    4. **Files are never pruned on their own.** An admin prunes them in **Settings ›
       Storage**: the size of the database and of the receipts directory, a **pie** of
       expired, expiring later and kept for ever, and a **bar for each coming year** of what
       expires in it, by category. Sizes are the files' sizes on disk; the section shows
       sizes and counts only, never what the files hold.
    5. **Prune 1,284 files (2.1 GB)** names what has expired. It previews them by category,
       any of which can be unticked, makes a verified backup (S14.6), asks the admin to type
       the count to confirm, removes the files, and records the file pruning in Activity
       with its counts. Each record keeps its row, amounts and links, and shows *File pruned
       Jan 3, 2034*. A pruned file stays in the backups made before it until backup pruning
       (S14.6) removes them, so a restore can bring it back until then.
