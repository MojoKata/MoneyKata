# Settings: Key storage

Read only. Everything the server stores is encrypted under one master key, which is the
recovery phrase: never stored, entered when the server starts, and changed only on the host.

![Settings: Key storage](shots/settings-keys.webp)

## Fingerprint

A short name for the key that reveals nothing about it, such as `mk-3f9a…c21e`.

## Unlocked

When the phrase was last entered. The server locks again at every restart, until someone
enters the phrase on the locked screen or with `moneykata keys unlock` on the host.

## Recovery phrase

The master key written as 12 words. It is shown once, at install, and never again: without it
nothing here, no backup, and no restart of the server opens. Check a copy once a year on the
host with `moneykata keys verify`.

## Test

Checks that the keyring on disk is the one the phrase unlocked, and that the database and a
secret open with the data key.

## Previous keys

The master keys this server was rotated away from, each with how many copies on this host still
need its phrase. A rotation re-wraps every copy it is told to, so the count is usually none; the
host's own snapshots and backups made before the rotation still open with that phrase for as
long as the host keeps them, and are yours to count. **Forget** drops a key from the list once
nothing needs it; destroy its sheet and password-manager entry then.

## Copies on this host

Every copy MoneyKata can see: the backups in the backup directory, the copies made before a
migration (`pre-upgrade/`) and what a restore set aside (`before-restore-*/`). Each carries its
own keyring and says how it opens: with this phrase, with this phrase but an earlier data key,
or only with a previous phrase. **Remove** deletes one, after your password. The host's own
snapshots and backups are copies too, outside this list.

## Re-encrypt

Makes a new data key and re-encrypts the database, the receipt files and every secret under it,
after a verified backup, and never while a backup runs. It asks for the recovery phrase, which
wraps the new data key, and your password again.

## The copies on this host {#copies-at-re-encryption}

For each copy, what the re-encryption does with it: **Re-encrypt** (the default) rewrites it
under the new data key, after the main job; **Delete** removes it; **Leave as it is** keeps it
under its old data key, which this phrase still opens. A copy that needs a previous phrase cannot
be rewritten here: leave it or delete it.
For when the data key may have been read: a memory dump or a debugging session on the live server,
or a master key or recovery phrase that leaked while any copy of the data directory or a backup
could have been taken with it. It closes nothing made before it: every earlier copy still opens
with the key it was made under, so a leak also means deleting those copies wherever they are. It
doesn't change the master key, which is rotated on the host with `moneykata keys rotate`.
