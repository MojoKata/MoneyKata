# Settings: Key storage

Read only. Everything the server stores is encrypted under one master key, a file on the host.

![Settings: Key storage](shots/settings-keys.webp)

## Fingerprint

A short name for the key that reveals nothing about it, such as `mk-3f9a…c21e`.

## Recovery phrase

The master key written as 12 words, the only way back if the key file is lost. Check a copy once a
year on the host with `moneykata keys verify`.

## Test

Checks the key file, unwraps the data key and opens the database and a secret.

## Previous key

A master key kept after a rotation, because the backups made before it hold the data key wrapped
under it. The date shown is when the backup directory's own pruning has removed the last of those
copies. A backup copied anywhere else (a NAS, a cloud bucket, a snapshot) is not counted: it still
opens with the previous key for as long as it exists, so count those copies yourself before the
old key and its phrase are destroyed.

## Re-encrypt

Makes a new data key and re-encrypts the database, the receipt files and every secret under it.
For when the data key may have been read: a memory dump or a debugging session on the live server,
or a master key or recovery phrase that leaked while any copy of the data directory or a backup
could have been taken with it. It closes nothing made before it: every earlier copy still opens
with the key it was made under, so a leak also means deleting those copies wherever they are. It
doesn't change the master key, which is rotated on the host with `moneykata keys rotate`.
