# Deploying MoneyKata

How to put a MoneyKata server where people can start testing it, on the first two hosts it
targets: **a fresh VM on Proxmox VE** and **TrueNAS**. Both run the same image, and
both serve HTTPS themselves on port 37373 with a self-signed certificate (`tls` mode,
requirements S13.3), which is what a test on a local network needs. A server the household
relies on goes behind its reverse proxy instead ([`operations.md`](operations.md) §2), and
`operations.md` is the runbook for everything after the install: upgrades, backups, restoring,
keys and the connector.

The steps were run on Proxmox VE 9.2 with a Debian 13 guest and Docker Engine 29, and on
TrueNAS Community Edition 25.10.7, with the image built on each host; their screenshots are from
those runs, and §5's are from a server built from the same source. A release's images are
published on ghcr.io (§2), and a host pulls them in place of that build.

## 1. What you need

- **A host**: amd64 or arm64 (S17.8.1), with **2 GB of memory** for MoneyKata (1 GB with
  receipt reading turned off, Settings › Receipts) and about **3 GB of disk** for the image
  and the data.
- **Internet access** from the host to `ghcr.io`, where the images are published, and to
  `raw.githubusercontent.com` for the example files.
- **Paper and a pen.** The server's master key is a **recovery phrase** of 12 words, shown
  once and never stored (S15). It is asked for after every start of the server: a reboot, an
  upgrade, a restart. Without it the data can't be opened, by anyone.
- **A browser** on the same network as the host.

## 2. The image

Each release is published as `ghcr.io/mojokata/moneykata:<version>`, one tag for amd64 and
arm64 (S17.8.2). Docker pulls it the first time a command below needs it; the image is under
1 GB. This guide installs **0.1.0**. GitHub records how each release's image was built, and
anyone can check that the one they pulled is it
([`gh`](https://cli.github.com/) installed):

```sh
gh attestation verify oci://ghcr.io/mojokata/moneykata:0.1.0 --owner MojoKata
```

To build it yourself instead, from a checkout of the source (about three minutes on a VM with
two cores), and to carry it to a host with no internet access:

```sh
docker buildx build -f web/install/Dockerfile -t ghcr.io/mojokata/moneykata:$(cat web/VERSION) --load .
docker save ghcr.io/mojokata/moneykata:0.1.0 | gzip > moneykata-0.1.0.tar.gz   # where it was built
docker load -i moneykata-0.1.0.tar.gz                                          # on the host
```

The **MoneyKata Connector** (S18), which signs in to institutions that have a driver, is a
second image and is not needed to try MoneyKata: accounts are kept current from the files
you upload. [`operations.md`](operations.md) §8 adds it.

## 3. A fresh VM on Proxmox VE

[Proxmox VE](https://www.proxmox.com/en/products/proxmox-virtual-environment/overview) runs
MoneyKata in a Debian VM with Docker. If Proxmox isn't installed yet:
[download](https://www.proxmox.com/en/downloads/proxmox-virtual-environment/iso) the ISO and
follow the [installation guide](https://pve.proxmox.com/wiki/Installation).

### 3.1 Make the VM

The quickest fresh VM is Debian's own cloud image with
[cloud-init](https://pve.proxmox.com/wiki/Cloud-Init_Support): no installer to click through.
In the Proxmox web UI, select the node and open **Shell**, then:

1. **Fetch the image**, Debian 13 from
   [Debian's cloud images](https://cloud.debian.org/images/cloud/):

   ```sh
   cd /root
   wget https://cloud.debian.org/images/cloud/trixie/latest/debian-13-genericcloud-amd64.qcow2
   ```

2. **Put your SSH public key** in a file, for the VM's user: paste it into
   `/root/moneykata.pub` (`nano /root/moneykata.pub`). It is the `.pub` file in `~/.ssh` on
   your own computer; `ssh-keygen -t ed25519` there makes one if you have none.
3. **Make the VM**: 2 cores, 4 GB of memory (MoneyKata needs 2 GB; the rest leaves the
   receipt reader room), a 32 GB disk made from the image, and a cloud-init drive. `120` is the VM's id
   and `local-lvm` the storage for its disks: use a free id, and your storage if it differs
   (**Datacenter › Storage** lists them; a ZFS install calls it `local-zfs`).

   ```sh
   qm create 120 --name moneykata --cores 2 --memory 4096 --cpu host --ostype l26 \
     --scsihw virtio-scsi-single --net0 virtio,bridge=vmbr0 --agent enabled=1 \
     --scsi0 local-lvm:0,import-from=/root/debian-13-genericcloud-amd64.qcow2,discard=on,ssd=1 \
     --ide2 local-lvm:cloudinit --boot order=scsi0 --serial0 socket --vga serial0 --onboot 1
   qm disk resize 120 scsi0 32G
   qm set 120 --ciuser debian --sshkeys /root/moneykata.pub --ipconfig0 ip=dhcp
   qm start 120
   ```

   For a fixed address, use `--ipconfig0 ip=192.168.1.50/24,gw=192.168.1.1` instead of
   `ip=dhcp`. `--onboot 1` starts the VM when the Proxmox host starts.

   ![The node's Shell after the qm commands](deploy/proxmox-shell.png)

4. **Find its address**: your router's list of DHCP leases shows it under the name
   `moneykata`, unless you gave it a fixed one. (The VM's **Console** shows only its boot and
   a login prompt, and the user has no password: sign in over SSH.) Once
   `qemu-guest-agent` runs (§3.2), the VM's **Summary** shows the address under **IPs**. The
   rest of this section calls it `192.168.1.50`.

   ![The VM's Summary, with its address under IPs](deploy/proxmox-summary.png)

### 3.2 Install Docker

Sign in to the VM (`ssh debian@192.168.1.50`) and install Docker Engine from
[Docker's own repository for Debian](https://docs.docker.com/engine/install/debian/):

```sh
sudo apt-get update
sudo apt-get install -y ca-certificates curl qemu-guest-agent
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
sudo tee /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/debian
Suites: $(. /etc/os-release && echo "$VERSION_CODENAME")
Components: stable
Signed-By: /etc/apt/keyrings/docker.asc
EOF
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker debian
sudo systemctl start qemu-guest-agent
sudo timedatectl set-timezone America/Chicago     # your own: backups and emails follow it
```

Sign out and in again, so `docker` works without `sudo`. `qemu-guest-agent` lets the Proxmox
UI show the VM's address on its **Summary**; it starts by itself at every boot after this one.

### 3.3 Set up

1. **Make a folder for the server**, with the release's example compose file:

   ```sh
   mkdir ~/moneykata && cd ~/moneykata
   curl -fsSLo compose.yaml https://raw.githubusercontent.com/MojoKata/MoneyKata/v0.1.0/web/install/compose.tls.yaml
   mkdir data backups && sudo chown 10001:10001 data backups
   ```

2. **Write its configuration**, `moneykata-tls.toml`, naming the address browsers will use, so
   the self-signed certificate covers it:

   ```sh
   cat > moneykata-tls.toml <<'EOF'
   [server]
   name = "moneykata"
   mode = "tls"
   port = 37373

   [paths]
   data = "/var/lib/moneykata"
   backups = "/var/backups/moneykata"

   [tls]
   names = ["192.168.1.50"]
   EOF
   ```

3. **Start it**: `docker compose up -d moneykata`, which first pulls the image (§2). Name the
   service: the compose file's other one is the connector, which needs a setup of its own
   before it starts (operations.md §8).
4. **Open it** in a browser: the welcome makes its master key and your account (§5).

### 3.4 After a reboot

The VM starts with the host (`--onboot 1`), and Docker starts MoneyKata with it
(`restart: unless-stopped`, S13.6), **locked**: open it and enter the phrase (§5).
`docker compose ps` in `~/moneykata` shows it `healthy` whenever it answers, locked or not;
`curl -k https://192.168.1.50:37373/healthz` says whether it is waiting for its phrase
(`locked`) or open (`ok`).

## 4. TrueNAS, installed manually

[TrueNAS Community Edition](https://www.truenas.com/truenas-community-edition/) 25.10
("Goldeye") runs apps as Docker Compose projects. These steps install MoneyKata by hand, as a
**custom app** from YAML; they work whether or not you use an app from TrueNAS's catalog, and
give full control of its datasets and configuration. If TrueNAS isn't installed yet:
[download](https://www.truenas.com/download/) the ISO and follow the
[installation guide](https://www.truenas.com/docs/scale/25.10/gettingstarted/install/).
The steps below use a pool named `tank` and the NAS's address `192.168.1.20`.

### 4.1 Pool, apps and datasets

1. **A pool**: **Storage › Create Pool**, if there isn't one.
2. **Apps**: open **Apps**. Until it has a pool it says *Apps Service Not Configured*:
   **Configuration › Choose Pool**, pick `tank`, **Choose**.
3. **Datasets**: **Datasets**, select `tank`, **Add Dataset**: name it `moneykata`, preset
   **Generic**, **Save**. Select `tank/moneykata` and add two datasets inside it the same
   way: `data` and `backups`. Separate datasets let snapshots and replication treat them
   apart (operations.md §2.3).

![The datasets](deploy/truenas-datasets.png)

### 4.2 The configuration

Open **System › Shell**; `sudo` asks for `truenas_admin`'s password. Keep the page open
until each command has finished. (SSH works as well, once it is turned on under **System ›
Services**; it is off by default.)

**Give the datasets to the container's user** (uid 10001) and **write the configuration**
beside them:

   ```sh
   sudo chown 10001:10001 /mnt/tank/moneykata/data /mnt/tank/moneykata/backups
   sudo tee /mnt/tank/moneykata/moneykata.toml >/dev/null <<'EOF'
   [server]
   name = "moneykata"
   mode = "tls"
   port = 37373

   [paths]
   data = "/var/lib/moneykata"
   backups = "/var/backups/moneykata"

   [tls]
   names = ["192.168.1.20"]
   EOF
   ```


### 4.3 Install the app

**Apps › Discover Apps**, then **⋮** (**More Options**, beside **Custom App**) **› Install
via YAML**. Name it `moneykata`, paste this as **Custom Config** (it is
`web/install/compose.truenas.yaml`), and **Save**:

```yaml
services:
  moneykata:
    image: ghcr.io/mojokata/moneykata:0.1.0
    restart: unless-stopped
    ports:
      - "37373:37373"
    volumes:
      - /mnt/tank/moneykata/data:/var/lib/moneykata
      - /mnt/tank/moneykata/backups:/var/backups/moneykata
      - /mnt/tank/moneykata/moneykata.toml:/etc/moneykata.toml:ro
      - /etc/localtime:/etc/localtime:ro
    read_only: true
    tmpfs:
      - /tmp
      - /run/moneykata:uid=10001,gid=10001,mode=0700
    cap_drop: [ALL]
    security_opt: ["no-new-privileges:true"]
    stop_grace_period: 10s
    logging:
      driver: json-file
      options: { max-size: "10m", max-file: "5" }
```

![Install via YAML](deploy/truenas-install-yaml.png)

The install pulls the image (§2) and finishes once the container answers: the app shows
**Running**. Then open it: the welcome makes its master key and your account (§5). The NAS's
time zone (**System › General Settings › Localization › Settings**) is the server's, for
backups and emails.

### 4.4 Snapshots and restarts

- **Data Protection › Periodic Snapshot Tasks › Add**: **Dataset** `tank/moneykata`,
  **Recursive** ticked, **Save**; by default it keeps two weeks of daily snapshots. Nothing
  in them opens without the phrase; operations.md §2.3 says what a snapshot is and isn't.
- After the NAS restarts, the app starts again by itself (`restart: unless-stopped`),
  **locked**, until someone enters the phrase (§5).
- Deleting the app (the app's **Delete**) offers **Remove Images**, ticked. Either way the
  datasets stay as they are, and the image is pulled again by the next install.

## 5. The welcome

1. Open `https://<address>:37373` (`https://192.168.1.50:37373` for the VM,
   `https://192.168.1.20:37373` for the NAS). The browser warns that the certificate isn't
   trusted, since MoneyKata made it itself: continue to the site.
2. A new server shows **Welcome to MoneyKata**. Have paper and a pen ready, then **Show my
   recovery phrase**.

   ![The welcome](deploy/moneykata-welcome.png)

3. **Write the 12 words down**, in order, with the fingerprint. They're the master key, and
   nothing shows them again: keep two copies in two places, one of them offline, and never
   with the backups (S15.6). Every visit, or another browser, shows other words; only the ones
   you confirm become the key. Then **I've written them down**.

   ![The recovery phrase (blurred here: never put a real one in a picture)](deploy/moneykata-phrase.png)

4. **Type three of the words back**, by their number, then **Make the key**. MoneyKata writes
   its key and opens.
5. **Set up the admin account**: a name, sex, an email address and a password of at least 12
   characters. You sign in as **`admin`** from now on (S10.1.2).

   ![The admin's account](deploy/moneykata-setup.png)

6. Then the **Dashboard**. **Users and Groups** invites the other testers. An invitation is
   an email: until **Settings › Email** has an SMTP server, each is written to the mail folder
   instead, and **Settings › Email** lists them, with **Open** to show the link to pass on.
   The help pane (**F1**) explains every screen, and `/demo` on the same address is the
   clickable mockup with sample data.

   ![The Dashboard](deploy/moneykata-dashboard.png)

**After every restart** the server is **locked** until someone enters the phrase: the page
asks for the 12 words, and sign-in follows. Instead of the browser, the phrase can be entered on
the host: `docker compose exec moneykata moneykata keys unlock` in `~/moneykata` on the VM;
`sudo docker exec -it ix-moneykata-moneykata-1 moneykata keys unlock` on TrueNAS.

![The locked screen](deploy/moneykata-locked.png)

**Check a copy of the phrase** once a year with **Verify key** in Settings › Key storage, and
whenever you make a new copy; the yearly alert opens it.

## 6. A new release

1. Change the image's tag to the new version: in `compose.yaml` on the VM, then
   `docker compose up -d moneykata`, which pulls it; on TrueNAS, **Edit** under **Application
   Info** opens **Edit App YAML**, and **Save** there pulls it and makes the container again.
2. Unlock it (§5). At the unlock the server copies the database aside and migrates it;
   operations.md §3 says how to go back.

## 7. When something's wrong

- **It won't start**: `docker compose ps` shows it `Restarting`, since it tries again about
  once a minute. `docker compose logs moneykata` shows why, in a line beginning `refusing to
  start:`; operations.md §5.1 lists the usual causes. On TrueNAS, the app's page lists its
  container under **Workloads**, and its **View Logs** icon shows the log.
- **The page won't load**: it is `https://`, on port 37373. A browser that refuses the
  certificate outright was given an address the certificate doesn't name: add it under
  `[tls] names` and restart; the server makes a new certificate.
- **It says it's locked**: it waits for the phrase after every start (§5).
- **A key nobody wrote down**: if someone else on the network finished the welcome first, the
  new server asks for words you never saw. Stop it, remove the keyring
  (`data/keyring`; on TrueNAS, in the `data` dataset), start it again, and the welcome comes
  back. Nothing is lost on a new server.
- **A lost phrase**: a running, unlocked server can still make a new one,
  `keys rotate` (operations.md §7). Once it restarts without one, nothing opens the data.
