# Running MoneyKata

How to install, upgrade, watch, back up and restore a MoneyKata server. The requirements say
what the server does (S13 architecture, S14 storage, S15 the master key, S17.8 packaging);
this page says what to do. Commands are run from the folder holding `compose.yaml`.

## 1. What runs where

One container, from one image (`moneykata:<version>`), as an unprivileged user (uid 10001),
listening on port 37373. It needs three things from the host, and one thing from a person:

| On the host     | In the container          | Holds                                          |
|-----------------|---------------------------|------------------------------------------------|
| `data/`         | `/var/lib/moneykata`      | the database, its keyring, receipts, linked copies, copies made before upgrades |
| `backups/`      | `/var/backups/moneykata`  | the daily backups                               |
| `moneykata.toml`| `/etc/moneykata.toml` (read only) | the configuration; never a secret       |

The master key is the **recovery phrase**, and it is never stored: the server starts locked
after every start (a restart, an upgrade, a reboot) until someone enters the phrase, on the
locked screen in a browser or with `docker compose exec moneykata moneykata keys unlock`
(S15.4). Nothing on the host holds a key, so the host can be snapshotted and backed up whole.

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

   Add `--platform linux/amd64,linux/arm64` for one image that also runs on arm64 (QEMU
   on the build machine: `docker run --privileged --rm tonistiigi/binfmt --install arm64`,
   once). `web/install/smoke.sh [linux/arm64]` builds both images for a platform and runs
   them once, as a release's gate (S17.8.1): the key from a phrase, a refused start, health,
   a sign-in, a receipt read, the connector's vault and unlock, and clean stops.
2. **Make the folders**, owned by the container's user:

   ```sh
   mkdir -p data backups && sudo chown 10001:10001 data backups
   ```

   Put `backups/` on a different disk from `data/` if you can.
3. **Make the master key**: `docker compose run --rm moneykata keys init`. It shows the
   **recovery phrase**, 12 words, and won't finish until you type three of them back. The
   phrase is the key: nothing of it is written, and nothing shows it again. Store it as
   S15.6 says: two copies in two places, one offline, never with the backups.
4. **Start it**: `docker compose up -d`, then point the reverse proxy at it and set
   `trusted_proxies` in `moneykata.toml` to the proxy's addresses. The listener speaks plain
   HTTP in `proxy` mode, so the compose file publishes it on the host's loopback only: a
   proxy running on the host reaches `127.0.0.1:37373`, and one running in the same compose
   project (`proxy/` is written that way) reaches `moneykata:37373` by name.
5. **Unlock it**: it starts locked. Open the app and enter the phrase on the locked screen,
   or run `docker compose exec moneykata moneykata keys unlock` and type it there. Do this
   after every start. A server with no users then makes `admin` with a default password; its
   first sign-in asks for a new password and an email address (S10.1.2).

### 2.1 On Proxmox

*Not yet tried on a real host: these steps follow the compose file.*

- **In a VM** (Debian or Ubuntu with Docker): as above. Give the VM 2 GB of memory, or 1 GB
  with receipt reading turned off (Settings › Receipts).
- **In an LXC container**: turn on **nesting** (Options › Features), install Docker inside,
  then as above. Keep `backups/` on a separate mount point backed by other storage.
- Proxmox's own backups of the VM or container can include everything: no key is on the
  disk, and nothing in them opens without the phrase.

### 2.3 On ZFS, with snapshots and replication

- Snapshot and replicate the datasets holding `data/` and `backups/` as you do the rest of
  the host: nothing in them opens without the phrase, and a raw send of an encrypted dataset
  opens only with the dataset's own key as well. Keep the phrase out of them.
- Every snapshot and replica is a **copy** (S15.8): it opens with the phrase of its day for
  as long as it exists, and MoneyKata cannot see or prune it. After a rotation or a leak,
  the snapshots made before are yours to destroy, on both ends of the replication.
- The live database file in a snapshot is crash-consistent at best; the verified copy in
  `backups/` from the same day is the one to restore from.

### 2.2 On TrueNAS

*Not yet tried on a real host: these steps follow the compose file.*

- Make two datasets, for data and backups, owned by uid 10001. Put backups on a different
  pool from data if you have one. Both can go into snapshot and replication tasks as they
  are: nothing in them opens without the phrase.
- Install it as a **custom app** from `compose.yaml`, with the two datasets as host paths in
  place of `./data` and `./backups`.
- Run the key step once from a shell on the NAS: `docker compose run --rm moneykata keys
  init`, and unlock after each start (§2 step 5).

## 3. Upgrading

1. Load the new image (`docker load`), change the image's tag in `compose.yaml` (both the
   `moneykata` service and the key commands), and run `docker compose up -d`.
2. At start the server copies the database into `data/pre-upgrade/` and checks the copy,
   then migrates it one revision at a time. The three newest copies are kept.
3. Unlock it (§2 step 5), then watch it come up: `docker compose ps` shows `healthy` once
   it answers; it shows `unhealthy` while locked.

**Going back** to the earlier release: stop it, set the old tag again, and restore the copy
made before the upgrade (or the last backup, §6). An older release refuses a database that a
newer one has migrated: it says so in a `refusing to start:` line (§5.1).

## 4. Backups

- **The host backs up the files.** MoneyKata's own backup never copies the receipt files,
  the linked copies or anything else in `data/`: your backup of the host does (snapshots,
  replication, any backup tool), and `data/` is safe to back up whole, since nothing in it
  opens without the phrase. Put `backups/` inside what the host backs up too.
- **Every day** at the time in Settings › Backups, the server writes a coherent, verified
  copy of the database with its keyring into `backups/moneykata-<date>-<time>/`, with a
  `manifest.json` of each file's size and hash, so the host's backup holds a consistent
  database beside the live one it also picks up. **Backup pruning** keeps the number of
  copies set there (14 by default) and removes older ones. No backup runs while a
  re-encryption does; each waits for the other.
- **Now**: `docker compose run --rm moneykata db backup`, with the phrase.
- A backup opens only with the phrase of its day; each carries its own keyring, and a
  rotation re-wraps them (§7).
- A backup that fails raises an alert for admins (and an email, for those who chose it).

## 5. Watching it

- **Health**: the image checks itself every 30 seconds (`moneykata health`, which asks
  `/healthz`). `docker compose ps` shows `starting`, `healthy` or `unhealthy`. From outside,
  point an uptime monitor (Uptime Kuma, for example) at `https://<your address>/healthz`: it
  answers `{"status": "ok", "version": …}` once the server is unlocked and ready, and 503
  with `"locked"` while it waits for the phrase, which is how anyone learns that a reboot
  happened and the phrase is needed.
- **Alerts**: problems that need someone show in Alerts for admins, and are emailed to those
  who chose it: a failed backup, a price source, email, the bitcoin node or a linked server
  failing for longer than Settings › Alerts allows, and a recovery phrase not confirmed.
- **Logs**: one line per event on the container's output, `docker compose logs -f moneykata`.
  They never hold amounts, names of accounts or payees, secrets or passwords. The example
  compose files keep five files of 10 MB each.
- **Space**: Settings › Storage shows the size of the database and the receipts, and what
  could be removed by file pruning (S14.10).

### 5.1 When it won't start

A problem only you can fix stops the start with one line beginning `refusing to start:`
and exit code 78. The compose file restarts it three times at most, then leaves it stopped.
`docker compose logs moneykata` shows the line. The usual causes:

| The line says                         | Do                                                      |
|---------------------------------------|---------------------------------------------------------|
| the keyring is missing               | a new server: `keys init` (§2); a rebuilt one: restore a backup (§6.2) |
| the config file has a problem         | fix `moneykata.toml` as the line says                    |

A server that started but stays locked after the phrase was entered says why in its log
(`refusing to unlock:`): a database from a newer MoneyKata (run that release or a later one,
or restore a backup made by this one), or a keyring the phrase doesn't open (the wrong
phrase, or the keyring from another server: the line names its fingerprint).

| The line says                         | Do                                                      |
|---------------------------------------|---------------------------------------------------------|
| the config file has a problem         | fix `moneykata.toml` as the line says                    |
| the data directory is in use          | another server is running on the same `data/`: stop it   |

## 6. Restoring

### 6.1 A backup onto the same server

1. Choose the backup: `ls backups/`. Check it first:
   `docker compose run --rm moneykata db verify-backup /var/backups/moneykata/<backup>`,
   which asks for the phrase.
2. Stop the server: `docker compose stop moneykata`.
3. Restore it: `docker compose run --rm moneykata db restore /var/backups/moneykata/<backup>`,
   with the phrase. It checks the backup again, refuses one from a newer release, and moves
   what it replaces (the database, its keyring and the linked copies) into
   `data/before-restore-<time>/` rather than deleting it. The receipt files stay where they
   are; Settings › Storage then counts any file the restored database no longer names, with
   Remove.
4. Start and unlock: `docker compose up -d`, then §2 step 5. The server opens the restored
   database and migrates it if it came from an earlier release. Linked households pull
   their copies again.
5. Once you're satisfied, remove `data/before-restore-<time>/`.

### 6.2 Onto a new host

1. Install the image and make the folders as in §2, but don't run `keys init`: the backup
   brings its keyring, and the phrase is the key.
2. Copy the backup folder into the new `backups/`, then restore, start and unlock as in
   §6.1, steps 3 and 4. The restore checks the phrase opens the backup before it changes
   anything.

### 6.3 Drills

- **Monthly**: `docker compose run --rm moneykata db verify-backup`, with the phrase. It
  checks the newest backup's hashes and that it opens, and changes nothing.
- **Yearly**: rehearse §6.2 into a throwaway folder on another machine or a scratch VM, with
  the phrase from its offline copy. That proves the backups, the phrase and these steps
  together. In the same sitting, check the phrase's copies are readable and run
  `docker compose run --rm moneykata keys verify` (S15.6.5). Every unlock after a restart is
  a check as well.

## 7. Keys

- **Unlock after a start**: `docker compose exec moneykata moneykata keys unlock`, or the
  locked screen in a browser. Nothing shows the phrase again: it is never stored.
- **Check a copy of the phrase**: `docker compose run --rm moneykata keys verify`.
- **Rotate the master key** (S15.7.1): with the server running, `docker compose exec
  moneykata moneykata keys rotate`. It needs no old phrase (the running server holds the
  data key), shows the new one and asks three words back, so it is also the way out of a
  lost phrase: do it before the server ever restarts. With the server stopped, `docker
  compose run --rm moneykata keys rotate` asks for the current phrase first. It then lists
  every copy on the host (backups, pre-upgrade copies, before-restore folders) and asks for
  each: **re-wrap** (Enter: its keyring under the new phrase, nothing else touched),
  **delete**, or **leave**; `--rewrap-all` answers for all of them. Store the new phrase; the
  server unlocks with it from its next start. Settings › Key storage then says which
  copies, if any, still need the previous phrase; the host's snapshots and backups made
  before the rotation always do, until you destroy them. When nothing needs it, **Forget**
  it there and destroy its copies.
- **Re-encrypt the data** (S15.7.2): Settings › Key storage › **Re-encrypt**, which asks for
  the phrase. For when the data key may have been read: a memory dump, or a leaked phrase
  (below).

### 7.1 When the key or phrase may have leaked

A leaked phrase is a leaked copy (S15.8): whoever has the phrase and any backup or copy of
`data/` made under it has everything in that copy, for ever. In this order:

1. Revoke and reissue every secret at its source: price-source keys, the bitcoin node's
   password, the SMTP password; unpair the connector and pair it again (§8).
2. Settings › Key storage › **Re-encrypt**, with the phrase, and wait for it to finish.
3. `docker compose exec moneykata moneykata keys rotate`, and store the new phrase in two
   places. The leaked phrase no longer unlocks the server.
4. Delete every backup and copy made before step 3, wherever it is: `backups/` (prune by
   hand: `rm -r backups/moneykata-<date>-*` for the old ones), the NAS or bucket, snapshots
   and VM images, `data/pre-upgrade/` and `data/before-restore-*/`. A copy you cannot delete
   is one the finder can read.
5. Then destroy the old phrase's sheet and password-manager entry.

## 8. The MoneyKata Connector

The connector (S18) keeps accounts current from their institutions, holding their credentials
where MoneyKata can't. It is the `connector` service in `compose.yaml`, from the
`moneykata-connector` image of the same version (`connector/Dockerfile`, built from
`connector/`), with a volume of its own, `connector-data`, that MoneyKata never mounts. It
publishes no port and only calls out: to MoneyKata, and to each driver's institution.

1. **Build its image** beside MoneyKata's: `docker buildx build -f connector/Dockerfile -t
   moneykata-connector:0.1.0 connector`, and carry it over as in §2.
2. **Install it once**: `docker compose run --rm connector init`. It prints **12 words** and
   won't finish until you type three back: save them in the household's password manager.
   They open the connector's vault, and nothing else can.
3. **Start it**: `docker compose up -d`. It starts **locked**, and MoneyKata alerts admins
   until it is unlocked.
4. **Unlock it after every start** (a restart, an update, the host's reboot):
   `docker compose exec connector moneykata-connector unlock`, then type the 12 words. They
   are never echoed, and never stored.
5. **Pair it**, with the vault unlocked: in MoneyKata, Settings › Connector › Pair shows a
   code; run `docker compose exec connector moneykata-connector pair <code>` and compare the
   fingerprints both sides show. Pairing makes the connector's sealing key and files its
   private half in the vault, so `pair` is refused while the vault is locked. The connector
   reaches MoneyKata at the address in the code (the public URL, or the link address), so
   that address must resolve from inside the container: on one host, the compose service
   name or the host's LAN address, not `localhost`.
6. **The Folder driver**: mount the folder read only into the connector at `/watch` (the
   commented line in `compose.yaml`), then start a folder Connection under Profile ›
   Connections naming a folder inside it (or nothing, for all of it) and its rules. The
   connector never reads outside that mount, whatever a Connection names.
7. **Credentials typed on the host** (the stricter way, S18.7.2): `docker compose exec
   connector moneykata-connector connect <connection id>`, which asks for each field without
   echo and files them in the vault.
8. **Watching it**: `docker compose exec connector moneykata-connector status` says whether
   it is paired and locked, when it last reported, and each Connection's state; MoneyKata's
   Settings › Connector shows the same from its reports, and alerts when the connector is
   locked or silent for 15 minutes.
9. **On another machine** instead (a laptop): run the same image there with its own
   `connector-data` volume, reaching MoneyKata's address, and add where it calls from to
   Settings › Network › Allowed to connect; nothing else changes.
10. **Unpair**: Settings › Connector › Unpair in MoneyKata, or `moneykata-connector unpair` on
    the host; either way the connector deletes the credentials it held for that server.
11. **Lost words**: `docker compose exec connector moneykata-connector reset` makes a new vault
    and new words; every Connection's credentials are entered again.
12. **Its logs** say what it did and what failed, never a credential, an amount or an account
    number beyond its last four digits: `docker compose logs -f connector`.
13. **A lost host or volume** (a stolen laptop, a disk sold with the volume on it): Unpair in
    MoneyKata at once. The copy holds the identity key, so until then whoever has it can
    report as the connector and post files; the vault stays closed without the words, so no
    sign-in and no sealed credential, before or after, opens for them. Then `init` a fresh
    vault on the new host, pair again, and have each owner enter their sign-ins again.
14. **A Connection that says *the server address changed***: its OFX server address was
    edited after the sign-in was filed. The connector sends nothing to the new address until
    the owner enters the sign-in again under Profile › Connections, which binds it to the new
    address.
