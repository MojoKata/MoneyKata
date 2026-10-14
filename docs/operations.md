# Running MoneyKata

How to install, upgrade, watch, back up and restore a MoneyKata server. The requirements say
what the server does (S13 architecture, S14 storage, S15 the master key, S17.8 packaging);
this page says what to do. Commands are run from the folder holding `compose.yaml`.

## 1. What runs where

One container, from one image (`moneykata:<version>`), as an unprivileged user (uid 10001),
listening on port 37373. It needs four things from the host:

| On the host     | In the container          | Holds                                          |
|-----------------|---------------------------|------------------------------------------------|
| `data/`         | `/var/lib/moneykata`      | the database, its keyring, receipts, linked copies, copies made before upgrades |
| `backups/`      | `/var/backups/moneykata`  | the daily backups                               |
| `keys/`         | `/etc/moneykata` (read only) | the master key file; never backed up with the data |
| `moneykata.toml`| `/etc/moneykata.toml` (read only) | the configuration; never a secret       |

`install/compose.yaml` runs it behind the household's reverse proxy (`proxy` mode);
`install/proxy/` has Caddy, nginx and haproxy examples. `install/compose.tls.yaml` runs its
own HTTPS with a self-signed certificate, for trying it on a local network.

### 1.1 Exposing only `/link/`

A linked server (S11) reaches this one at its own address under `/link/`; there is no
separate port. To let a linked household in without exposing the app, have the reverse proxy
pass only that path from the outside, for example with Caddy:

```
money.example.org {
    @link path /link/*
    handle @link {
        reverse_proxy moneykata:37373
    }
    respond 404
}
```

The app itself (`/ui`) stays reachable only on the household's own network or overlay.

## 2. Installing

1. **Get the image.** There is no registry: build it on any amd64 machine and carry it over.

   ```sh
   docker buildx build -f web/install/Dockerfile -t moneykata:$(cat web/VERSION) .
   docker save moneykata:0.1.0 | gzip > moneykata-0.1.0.tar.gz      # on the build machine
   docker load < moneykata-0.1.0.tar.gz                              # on the server
   ```

   Add `--platform linux/amd64,linux/arm64` for one image that also runs on arm64.
2. **Make the folders**, owned by the container's user:

   ```sh
   mkdir -p data backups keys && sudo chown 10001:10001 data backups
   ```

   Put `backups/` on a different disk from `data/` if you can.
3. **Make the master key**: `docker compose run --rm keys-init`. It shows the **recovery
   phrase**, 12 words, and won't finish until you type three of them back. Store the phrase
   as S15.6 says: two copies in two places, one offline, never with the backups.
4. **Start it**: `docker compose up -d`, then point the reverse proxy at port 37373 and set
   `trusted_proxies` in `moneykata.toml` to the proxy's addresses. A server with no users
   makes `admin` with a default password; its first sign-in asks for a new password and an
   email address (S10.1.2).

### 2.1 On Proxmox

*Not yet tried on a real host: these steps follow the compose file.*

- **In a VM** (Debian or Ubuntu with Docker): as above. Give the VM 2 GB of memory, or 1 GB
  with receipt reading turned off (Settings › Receipts).
- **In an LXC container**: turn on **nesting** (Options › Features), install Docker inside,
  then as above. Keep `backups/` on a separate mount point backed by other storage.
- Proxmox's own backups of the VM or container hold the master key if `keys/` is inside it.
  Either keep `keys/` on a mount point left out of those backups, or treat those backups as
  holding the key: never store them with MoneyKata's own backups.

### 2.2 On TrueNAS

*Not yet tried on a real host: these steps follow the compose file.*

- Make three datasets, for data, backups and keys; set the first two's owner to uid 10001.
  Put backups on a different pool from data if you have one, and leave the keys dataset out
  of replication and snapshot tasks that leave the box.
- Install it as a **custom app** from `compose.yaml`, with the three datasets as host paths
  in place of `./data`, `./backups` and `./keys`.
- Run the key step once from a shell on the NAS: `docker compose run --rm keys-init`.

## 3. Upgrading

1. Load the new image (`docker load`), change the image's tag in `compose.yaml` (both the
   `moneykata` service and the key commands), and run `docker compose up -d`.
2. At start the server copies the database into `data/pre-upgrade/` and checks the copy,
   then migrates it one revision at a time. The three newest copies are kept.
3. Watch it come up: `docker compose ps` shows `healthy` once it answers.

**Going back** to the earlier release: stop it, set the old tag again, and restore the copy
made before the upgrade (or the last backup, §6). An older release refuses a database that a
newer one has migrated: it says so in a `refusing to start:` line (§5.1).

## 4. Backups

- **Every day** at the time in Settings › Backups, the server copies the database, its
  keyring and the receipts into `backups/moneykata-<date>-<time>/`, checks the copy opens, and
  writes a `manifest.json` with each file's size and hash. **Backup pruning** keeps the number
  of copies set there (14 by default) and removes older ones.
- **Now**: `docker compose exec moneykata moneykata db backup`.
- A backup is as encrypted as the data: it opens only with the master key or its recovery
  phrase. You can copy `backups/` as it is to a NAS, another disk or a cloud bucket, as long as
  the phrase and the key file never go with it.
- Linked copies are left out: after a restore they are pulled again from their sources.
- A backup that fails raises an alert for admins (and an email, for those who chose it).

## 5. Watching it

- **Health**: the image checks itself every 30 seconds (`moneykata health`, which asks
  `/healthz`). `docker compose ps` shows `starting`, `healthy` or `unhealthy`. From outside,
  point an uptime monitor (Uptime Kuma, for example) at `https://<your address>/healthz`: it
  answers `{"status": "ok", "version": …}` once the server is ready, and 503 while starting.
- **Alerts**: problems that need someone show in Alerts for admins, and are emailed to those
  who chose it: a failed backup, a price source, email, the bitcoin node or a linked server
  failing for longer than Settings › Alerts allows, and a recovery phrase not confirmed.
- **Logs**: one line per event on the container's output, `docker compose logs -f moneykata`.
  They never hold amounts, names of accounts or payees, secrets or passwords. The example
  compose files keep five files of 10 MB each.
- **Space**: Settings › Storage shows the size of the database and the receipts, and what
  could be removed by database pruning (S14.10).

### 5.1 When it won't start

A problem only you can fix stops the start with one line beginning `refusing to start:`
and exit code 78. The compose file restarts it three times at most, then leaves it stopped.
`docker compose logs moneykata` shows the line. The usual causes:

| The line says                         | Do                                                      |
|---------------------------------------|---------------------------------------------------------|
| the key file is missing or its mode is wrong | restore the key from its phrase (§6.2), or fix the file's owner and mode as the line says |
| the key does not open the database   | the wrong key is mounted: mount the one whose fingerprint the line names |
| the database is from a newer MoneyKata | run that release or a later one; or restore a backup made by this one |
| the config file has a problem         | fix `moneykata.toml` as the line says                    |
| the data directory is in use          | another server is running on the same `data/`: stop it   |

## 6. Restoring

### 6.1 A backup onto the same server

1. Choose the backup: `ls backups/`. Check it first:
   `docker compose run --rm moneykata db verify-backup /var/backups/moneykata/<backup>`.
2. Stop the server: `docker compose stop moneykata`.
3. Restore it: `docker compose run --rm moneykata db restore /var/backups/moneykata/<backup>`.
   It checks the backup again, refuses one from a newer release, and moves what it replaces
   (the database, its keyring, the receipts and the linked copies) into
   `data/before-restore-<time>/` rather than deleting it.
4. Start: `docker compose up -d`. The server opens the restored database and migrates it if
   it came from an earlier release. Linked households pull their copies again.
5. Once you're satisfied, remove `data/before-restore-<time>/`.

### 6.2 Onto a new host

1. Install the image and make the folders as in §2, but don't run `keys-init`.
2. Write the key back from the recovery phrase:
   `docker compose run --rm keys-init keys init --from-phrase`. It checks the phrase's
   checksum and writes the key file with the right owner and mode.
3. Copy the backup folder into the new `backups/`, then restore and start as in §6.1, steps 3
   and 4. The restore checks the key opens the backup before it changes anything.

### 6.3 Drills

- **Monthly**: `docker compose exec moneykata moneykata db verify-backup`. It checks the
  newest backup's hashes and that it opens with the master key, and changes nothing.
- **Yearly**: rehearse §6.2 into a throwaway folder on another machine or a scratch VM, with
  the phrase from its offline copy. That proves the backups, the phrase and these steps
  together. In the same sitting, check the phrase's copies are readable and run
  `moneykata keys verify` (S15.6.5).

## 7. Keys

- **Show the phrase again**: `docker compose run --rm moneykata keys phrase`.
- **Check a copy of the phrase**: `docker compose run --rm moneykata keys verify`.
- **Rotate the master key** (S15.7.1): `docker compose run --rm keys-rotate`, store the new
  phrase, then `docker compose restart moneykata`. Keep the previous key, as
  `moneykata.toml` lists it, until backup pruning has removed every backup made before the
  rotation: Settings › Key storage says when.
- **Re-encrypt the data** (S15.7.2): Settings › Key storage › **Re-encrypt**.
