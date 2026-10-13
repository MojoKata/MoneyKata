"""moneykata.toml: what the operator sets on the host (requirements S13.3, S15.4, S17.8).

Everything a user or admin can change at run time is a Setting in the database (settings.py).
This file holds only what the server needs before the database is open, and it never holds a
secret.
"""

import ipaddress
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

DEFAULT_PORT = 37373
DEFAULT_CONFIG = Path("/etc/moneykata.toml")


class RefuseStart(Exception):
    """A reason only an operator can fix: the server says why on one line and exits 78."""


@dataclass(frozen=True)
class PreviousKey:
    """A master key kept after a rotation until the backups that need it are pruned."""

    path: Path
    fingerprint: str


@dataclass(frozen=True)
class Config:
    name: str
    mode: Literal["proxy", "tls"]
    data_dir: Path
    backup_dir: Path
    key_file: Path
    host: str = "0.0.0.0"  # noqa: S104 - all of the container's interfaces (S13.3)
    port: int = DEFAULT_PORT
    trusted_proxies: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...] = ()
    tls_cert: Path | None = None
    tls_key: Path | None = None
    previous_keys: tuple[PreviousKey, ...] = ()
    dev: bool = False
    stubs: bool = False
    path: Path | None = None
    mail_folder: Path | None = None
    cert_names: tuple[str, ...] = ()  # more names for the self-signed certificate

    @property
    def db_path(self) -> Path:
        return self.data_dir / "moneykata.db"

    @property
    def keyring_path(self) -> Path:
        return self.data_dir / "keyring"

    @property
    def receipts_dir(self) -> Path:
        return self.data_dir / "receipts"

    @property
    def tls_dir(self) -> Path:
        return self.data_dir / "tls"

    @property
    def mail_dir(self) -> Path:
        """Where emails are written while SMTP is not set up (and always in dev mode)."""
        return self.mail_folder or self.data_dir / "mail"

    @property
    def outbox_dir(self) -> Path:
        """Emails waiting to go out through SMTP; each is removed once the server took it."""
        return self.data_dir / "outbox"


def _path(table: dict, key: str, where: str) -> Path:
    value = table.get(key)
    if not isinstance(value, str) or not value:
        raise RefuseStart(f"{where}: [{key}] must be set to a path")
    return Path(value)


def load(path: Path) -> Config:
    """Read and check the config file; any problem refuses the start."""
    try:
        raw = tomllib.loads(path.read_text())
    except FileNotFoundError:
        raise RefuseStart(f"config file {path} does not exist") from None
    except PermissionError:
        raise RefuseStart(f"config file {path} cannot be read by this account") from None
    except tomllib.TOMLDecodeError as e:
        raise RefuseStart(f"config file {path} is not valid TOML: {e}") from None
    return parse(raw, str(path), path)


def parse(raw: dict, where: str, path: Path | None = None) -> Config:
    known = {"server", "paths", "keys", "tls"}
    unknown = set(raw) - known
    if unknown:
        raise RefuseStart(f"{where}: unknown section [{sorted(unknown)[0]}]")
    server = raw.get("server", {})
    paths = raw.get("paths", {})
    keys = raw.get("keys", {})
    tls = raw.get("tls", {})

    name = server.get("name", "moneykata")
    if not isinstance(name, str) or not name.strip():
        raise RefuseStart(f"{where}: server.name must be a non-empty string")
    mode = server.get("mode", "proxy")
    if mode not in ("proxy", "tls"):
        raise RefuseStart(f'{where}: server.mode must be "proxy" or "tls", not {mode!r}')
    port = server.get("port", DEFAULT_PORT)
    if not isinstance(port, int) or not 1 <= port <= 65535:
        raise RefuseStart(f"{where}: server.port must be a port number")
    host = server.get("host", "0.0.0.0")  # noqa: S104
    proxies = []
    for entry in server.get("trusted_proxies", []):
        try:
            proxies.append(ipaddress.ip_network(entry, strict=False))
        except (ValueError, TypeError):
            raise RefuseStart(
                f"{where}: server.trusted_proxies: {entry!r} is not an address or network"
            ) from None

    data_dir = _path(paths, "data", f"{where} [paths]")
    backup_dir = _path(paths, "backups", f"{where} [paths]")
    key_file = _path(keys, "master", f"{where} [keys]")
    previous = []
    for entry in keys.get("previous", []):
        if not isinstance(entry, dict) or "path" not in entry or "fingerprint" not in entry:
            raise RefuseStart(f"{where}: keys.previous entries need a path and a fingerprint")
        previous.append(PreviousKey(Path(entry["path"]), str(entry["fingerprint"])))

    cert = tls.get("cert")
    key = tls.get("key")
    if bool(cert) != bool(key):
        raise RefuseStart(f"{where}: [tls] needs both cert and key, or neither")
    names = tls.get("names", [])
    if not isinstance(names, list) or not all(isinstance(n, str) and n.strip() for n in names):
        raise RefuseStart(f"{where}: [tls] names must be a list of host names or addresses")

    for p, label in ((data_dir, "data"), (backup_dir, "backups"), (key_file, "master key")):
        if not p.is_absolute():
            raise RefuseStart(f"{where}: the {label} path must be absolute")
    _check_apart(key_file, data_dir, backup_dir)

    return Config(
        name=name.strip(),
        mode=mode,
        host=host,
        port=port,
        trusted_proxies=tuple(proxies),
        data_dir=data_dir,
        backup_dir=backup_dir,
        key_file=key_file,
        tls_cert=Path(cert) if cert else None,
        tls_key=Path(key) if key else None,
        cert_names=tuple(n.strip() for n in names),
        previous_keys=tuple(previous),
        path=path,
    )


def _check_apart(key_file: Path, data_dir: Path, backup_dir: Path) -> None:
    """The key never lands in a backup: it sits outside the data and backup directories."""
    key = key_file.resolve()
    for d, label in ((data_dir, "data"), (backup_dir, "backup")):
        if key.is_relative_to(d.resolve()):
            raise RefuseStart(f"the master key {key_file} is inside the {label} directory")
    if backup_dir.resolve().is_relative_to(data_dir.resolve()):
        raise RefuseStart("the backup directory is inside the data directory")
