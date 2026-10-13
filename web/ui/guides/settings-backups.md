# Settings: Backups

Daily copies of the database and receipts, made, checked and pruned by the server.

![Settings: Backups](shots/settings-backups.webp)

## Time of day

When the daily backup runs.

## Copies kept

How many backups stay; older ones are deleted. 14 by default.

## Back up now

Makes a backup now.

## Restoring

Backups are encrypted as the data is, and open with the master key's recovery phrase. The directory
is set on the host, outside the data directory.
