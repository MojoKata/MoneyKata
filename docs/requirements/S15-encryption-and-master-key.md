# S15. Encryption and the master key

This section is for the admin who installs and runs the server. It explains what MoneyKata
encrypts and how, how to back up and protect the master key with its recovery phrase, and
what key rotation does.

1. **What is encrypted, and what is not.**
   1. **The database**: the whole main database, with SQLCipher, including the full text read
      from receipts and the thumbnails.
   2. **The receipt files**: each in its own encrypted file (S9.2).
   3. **Secrets, each on its own as well**: every *secret* the server holds so it can act for
      its users: price-source API keys, the bitcoin node's credentials, the SMTP password,
      and this server's private link key (S11.1).
   4. **Backups**, which are copies of the encrypted database and files (S14.6).
   5. **Encrypted under their own access keys, not the master key**: everything a link
      brings in, in its linked copy (S11.9). The master key cannot open it, so neither losing
      nor rotating the master key touches it.
   6. **Hashed, never encrypted**: passwords (argon2id) and session, invitation, reset and
      confirmation tokens (SHA-256 of a random value). They never need to be read back, so
      there is no key that could reveal them.
   7. **Not encrypted**: the configuration file, the logs, which must never hold amounts,
      names or secrets, and the key file itself (S15.4).
2. **No external key service.** MoneyKata keeps its master key in a file on the host.
   HashiCorp Vault, cloud KMSs (AWS, GCP, Azure), HSMs and TPM sealing are **not supported**.
   On a household server, an external service adds a dependency that must be running,
   backed up and secured itself, for little gain over a key file with good offline backups.
3. **How it works: three levels of keys.**
   1. **The master key**: 128 random bits in one file on the host (S15.4), made once at
      install. It is backed up as its **recovery phrase**: the same 128 bits written as 12
      words from the BIP39 English word list, the last word carrying a checksum. MoneyKata
      uses the words only as a way to write the key down. It never applies BIP39's wallet
      derivation to them. The master key encrypts one thing: the data key. It is never
      stored in the database, never written to a log, never sent over the network, never
      shown in the UI, and never included in the server's backups.
   2. **The data key**: 256 random bits, made at install, stored only **wrapped**
      (AES-256-GCM) under a key derived from the master key with HKDF-SHA256 (label
      `moneykata master`). The wrapped data key sits in the data directory (`keyring`), so it
      travels with every backup. From the data key, HKDF-SHA256 derives, each under its own
      label:
      1. the **database key**, which SQLCipher uses as its raw key;
      2. the **receipts key**, an X25519 key pair: receipt files use the streaming format of
         S11.9.6 with this key in place of a linked copy's key;
      3. the **secrets key**, which wraps the secrets' own data keys.
   3. **Secret data keys**: each secret gets its own random 256-bit data key when it is
      saved. The server encrypts the value with **AES-256-GCM** under it, using a random
      96-bit nonce. The **associated data** names where the secret belongs: record type, the
      record's stable id, and field. The secret's data key is then wrapped under the secrets
      key. The row stores the ciphertext, its nonce and the wrapped key.
   4. **Using a secret**: only when a task needs it (a price refresh, a bitcoin wallet read, an email). The
      server unwraps its data key, decrypts the value, uses it for that one call and discards
      it. GCM authenticates every step, so a tampered ciphertext, a wrong key, or a ciphertext
      copied onto another record or field fails to decrypt instead of producing a wrong value.
      Secrets are encrypted on their own as well as inside the database, so that a database
      opened for maintenance (S14.7) still shows no secret.
   5. **The master key id** is the first 16 hex digits of `SHA-256("moneykata key id" ‖ key)`.
      It identifies a key without revealing it. Its short form (`mk-3f9a…c21e`) is the
      **fingerprint** shown in Settings, on the recovery sheet and in the commands below. The
      wrapped data key records which master key wrapped it.
   6. **Why three levels**: rotating the master key re-wraps one 32-byte data key and nothing
      else; the database and the files never need re-encrypting for it; and each secret still
      stands or falls on its own, with associated data that stops anyone with write access to
      the database from moving one user's API key onto a record they control.
   7. **What a stolen copy gives away**: a copy of the data directory or a backup **without
      the master key** (the key file or its recovery phrase) reveals nothing but sizes and
      dates. With the key, it reveals everything in that copy. The key file sits on the
      host's own disk, so a stolen server disk holds both: that is why disk encryption on the
      host still matters (S15.6.7). An attacker who has root on the running server can read
      the key and the database, and no design changes that. This is why the key and the
      backups are kept apart (S15.6), and why S15.8 says to revoke secrets at their source
      when a key may have leaked.
4. **The key file.**
   1. **Where**: `/etc/moneykata/master.key` in the container, from a key directory on the
      host mounted there (S17.8), named in `moneykata.toml` under `[keys]`. It must be outside
      the data directory and outside the backup directory, so it never lands in a backup.
   2. **Owner and mode**: readable only by the server's account (uid 10001, mode `0400`).
      The running server mounts the key directory read only. There is no separate keys
      process. Never world- or group-readable, never writable by the server.
   3. **Made by** `moneykata keys init`, which writes 16 bytes from the operating
      system's random source with those modes, makes and wraps the data key, and refuses to
      overwrite an existing key. It then shows the **recovery phrase** and asks for three of
      its words back (S15.6.1). Until they are typed correctly, the key is not saved and the
      server cannot start.
   4. **Checked at start**: the server **refuses to start** (exit 78, S13.6) when the file is
      missing, is not exactly 16 bytes, can be written by anyone but root, can be read by
      anyone but its account, sits inside the data or backup directory, or does not unwrap
      the data key. `moneykata keys
      check` runs the same checks without starting the server.
   5. **Never** baked into the image, passed as an environment variable, or kept in a volume
      that is backed up with the data. A Docker secret works in place of the mounted
      directory.
   6. **Commands**, run on the host as one-off containers of the same image (`docker compose
      run --rm moneykata keys verify`); only `init` and `rotate` mount the key directory
      writable, and only `rotate` mounts `moneykata.toml` writable, to record the previous
      key in it. `rotate` checks it can write all three before it changes anything. Nothing an admin does day to day: `moneykata keys init`,
      `check`, `fingerprint`, `phrase` (shows the recovery phrase again), `verify` and
      `rotate` (S15.6, S15.7), and `moneykata db shell` (S14.7).
5. **What losing it costs.** Everything this server holds is encrypted under the master
   key, so **losing both the key file and its recovery phrase loses all of it**: the
   database, the receipts and every backup. There is no back door, and no one can recover
   it, including the people who make MoneyKata.
   1. **The key file lost, the phrase kept** (a failed disk, a rebuilt host): write the key
      back from the phrase with `moneykata keys init --from-phrase` and restore. Nothing
      is lost.
   2. **The phrase lost, the key file kept**: nothing is lost yet, but the next failure will
      be. Show the phrase again with `moneykata keys phrase` and back it up at once, or
      rotate the key (S15.7) and back up the new phrase.
   3. Linked copies are not affected either way: they open with their own access keys, and
      are pulled again from their sources (S11.9.9).
6. **Backing up and protecting the master key.**
   1. **Back it up as it is made.** `keys init` and `keys rotate` show the **recovery
      phrase**, 12 numbered words, with the fingerprint, the server's name and the date, and
      will not finish until three words chosen at random are typed back. `moneykata keys
      phrase` shows it again at any time, and `--file PATH` writes it as a recovery sheet to
      print. Each word is recognised by its first four letters, and the last word's checksum
      catches most mistakes when the phrase is typed back in.
   2. **Keep at least two copies in two places**, at least one of them offline. For example:
      1. the printed sheet in a fire-resistant safe at home or a bank safe-deposit box;
      2. a secure note in the household's password manager (Bitwarden, 1Password, KeePassXC),
         in a vault that the second person below can also open;
      3. optionally, a USB stick holding the export encrypted with a passphrase (`age -p` or
         `gpg -c`), stored apart from the first copy.
   3. **Never keep it with the database backups**: not in the same directory, on the same
      disk, in the same cloud bucket, or in the same archive. A backup that holds both the
      database and the key protects nothing.
   4. **Never put it** in git, a ticket, a chat message, email, a shared drive, a container
      image, or a screenshot.
   5. **Check the backup.** `moneykata keys verify` asks for the whole phrase and says
      whether it matches the running key, without changing anything. Settings › Key storage
      records each confirmation: who, which fingerprint, and when. Check the copies once a
      year: that the sheet is readable, and that the password manager entry still verifies.
      Settings reminds admins when a year has passed.
   6. **Two people should be able to recover it**: the admin and one trusted person, such as a
      partner, an executor or an adult child. Write down where the copies are, alongside the
      household's estate documents, because financial records are needed exactly when the
      person who set up the server is not available.
   7. **Protect the host as well**: full-disk encryption on the server (LUKS, FileVault,
      BitLocker or ZFS native encryption), because the key file sits on the same disk as the
      data, and root access limited to the people who run the server. Backups are already
      encrypted, so they can go to a NAS or a cloud bucket as they are, as long as the
      recovery phrase never goes with them.
   8. **Restoring onto a new host**: install MoneyKata, write the key from the recovery
      phrase with `moneykata keys init --from-phrase` (which checks the checksum and,
      given the backup, the fingerprint, and sets the owner and mode), restore the backup with
      `moneykata db restore`, and start. The restore runs with the server stopped (the
      server holds a lock on the data directory while it runs): it checks the backup as
      `db verify-backup` does, refuses one from a newer release, and moves what it replaces
      (the database, its keyring, the receipts and the linked copies) aside into
      `before-restore-<time>/` in the data directory rather than deleting it. At start the server unwraps the data key, opens
      the database, and reports anything it cannot open. `operations.md` has the step-by-step runbook, and a check rehearses
      it.
7. **Key rotation.** There are two kinds, and they do different things.
   1. **Rotating the master key** replaces the key file and its recovery phrase, and
      re-wraps the data key under the new key. Nothing else is re-encrypted. It is done on
      the host:
      1. `moneykata keys rotate` makes a new key, shows its recovery phrase and asks for
         three words back, re-wraps the data key in one step, and moves the current key to
         the `previous` list in `moneykata.toml` (with its fingerprint);
      2. **back up the new phrase at once** (S15.6), then restart the server;
      3. verify the new phrase (`keys verify`);
      4. **keep the previous key until every backup made before the rotation has been
         pruned** (backup pruning, S14.6, keeps 14 copies by default: two weeks of daily
         backups, and fewer days when backups are also made by hand), because those
         backups hold the data key wrapped under it. Then remove it from `previous`, delete
         the old key file, and destroy its recovery sheet and password-manager entry.
         Settings names the date after which the previous key is no longer needed.
   2. **Re-encrypting** (Settings › Key storage › **Re-encrypt**, admins) makes a new data
      key: the database is re-keyed (`PRAGMA rekey`), receipt files are re-encrypted a few
      at a time while the server keeps serving, and every secret gets a fresh data key and
      nonce. The master key is unchanged. Settings › Key storage shows the progress. It is
      rarely needed: only when the data key may have been exposed, such as a memory dump or
      a debugging session on the live server.
   3. **What rotation does not do**:
      1. It does not change the secrets themselves. A price source's API key is the same key after
         rotation, and anyone who already read it can still use it.
      2. It does not protect copies made before it. A backup taken before a master-key
         rotation can still be opened with the old key, which is why the old key is
         destroyed once those backups are gone.
      3. It does not touch passwords, which are hashed, or linked copies, which have their
         own access keys.
   4. **Rotation is recorded** in Activity for admins: who, when, and the old and new
      fingerprints. Key material is never recorded.
8. **Best practices for rotation.**
   1. **Rotate the master key when there is a reason**:
      1. someone who had root on the server, or held a copy of the key, no longer should;
      2. a copy of the key may have been exposed: a lost recovery sheet, a compromised
         password-manager vault, a disk with the key file sold, recycled or lost;
      3. the server was compromised (and after rebuilding it).
   2. **Otherwise, rotate on a calm schedule: once a year is plenty** for a household server.
      Every rotation means a new backup of the key in two places and an old one to destroy
      later. Rotating more often adds that work and the risk of a key with no backup, without
      adding security. Settings shows the key's age and reminds admins after a
      configurable period (12 months by default; off is allowed).
   3. **When a key may have leaked, rotation is the second step, not the first.** First
      **revoke and reissue the secrets at their source**: new price-source keys, a new
      password for the bitcoin node, a new SMTP password. Then rotate the master key, so
      future copies are wrapped under a key nobody else has. Rotation alone leaves every
      secret readable from any old copy.
   4. **Never rotate without a tested backup of the new key.** Rotate when there is time to
      make and verify the backups the same day, not at the end of a maintenance window.
   5. **Keep the previous key exactly as long as the backups that need it**, then destroy every
      copy of it. A previous key kept for ever is a second key to protect.
   6. **Re-encrypt** only for its specific reason (S15.7.2). It is not a substitute for
      rotating the master key, or for revoking a leaked secret.
