"""The connector's loop (requirements S18.5, S18.7, S18.8, docs/connector-protocol.md): every
5 minutes a signed report to MoneyKata, answered with what waits; sealed credentials collected
into the vault, bound to the host they may be sent to; each Connection's driver run at its
interval, never against a host its credentials aren't bound to; what it fetched posted for its
accounts, a post refused for a limit kept for a later run."""

import json
import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import client, keys, sealed
from .client import Egress, ServerError, Transport
from .drivers import Account, Driver, File, registry
from .vault import Vault, VaultError

log = logging.getLogger("connector")
REPORT_SECONDS = 300


@dataclass
class ConnectionState:
    id: str
    driver: str
    label: str
    settings: dict
    accounts: list[Account]
    state: str = "new"
    message: str | None = None
    last_run: float | None = None
    last_added: int | None = None
    found: list[dict] = field(default_factory=list)
    sign_in: str | None = None
    backlog: list[File] = field(default_factory=list)


class Core:
    def __init__(self, data: Path, transport: Transport | None = None, drivers=None):
        self.data = data
        data.mkdir(parents=True, exist_ok=True)
        self.vault = Vault(data / "vault.json")
        self.egress = Egress()
        self.transport = transport or Transport(self.egress)
        self.drivers: dict[str, Driver] = drivers or registry()
        for d in self.drivers.values():
            self.egress.allow(*d.hosts)
        self.pairing = keys.load(data / "pairing.json")
        self.server: client.Server | None = None
        self.connections: dict[str, ConnectionState] = {}
        self.last_report: float | None = None
        self.last_error: str | None = None
        self._lock = threading.RLock()
        self._wake = threading.Event()
        self._stop = threading.Event()
        if self.pairing:
            self._attach(self.pairing)

    # ----- pairing -----

    def _attach(self, pairing: keys.Pairing) -> None:
        self.pairing = pairing
        self.egress.allow(_host(pairing.address))
        hi = client.hello(self.transport, pairing.address, pairing.pins())
        if hi.get("fingerprint") != pairing.server_fp:
            raise ServerError("fingerprint-mismatch", "The server's key isn't the one paired with.")
        self.server = client.Server(
            pairing, self.transport, client.server_key(hi), self._certificate
        )

    def _certificate(self, pinned: str, following: str | None) -> None:
        """MoneyKata announced its next certificate key, in a signed answer, or started using
        the one it announced: the pairing keeps the keys it may present (protocol §1.2)."""
        with self._lock:
            p = self.pairing
            if p is None:
                return
            p.cert, p.cert_next = pinned, following
            keys.save(self.data / "pairing.json", p)

    def pair(self, code: str) -> str:
        """`moneykata-connector pair <code>` (S18.4.2): check the server's fingerprint against
        the code, make the keys, introduce the connector. Returns its fingerprint to compare.
        The vault must be unlocked: the sealing key's private half goes into it (S18.4.5)."""
        if self.vault.locked:
            raise VaultError("unlock the vault first: the sealing key is kept in it")
        c = decode_code(code)
        self.egress.allow(_host(c["a"]))
        cert = c.get("t") if isinstance(c.get("t"), str) else None
        hi = client.hello(self.transport, c["a"], frozenset([cert]) if cert else None)
        if hi.get("fingerprint") != c["f"]:
            raise ServerError(
                "fingerprint-mismatch",
                "The server at that address doesn't have the key the code names: nothing sent.",
            )
        private, public = keys.new_sealing_key()
        pairing = keys.make(self.data / "pairing.json", c["a"], c["f"], public, cert)
        server = client.Server(pairing, self.transport, client.server_key(hi), self._certificate)
        out = server.call(
            "/connector/v1/pair",
            {"code": code, "sealingKey": keys.b64(public), "version": client.VERSION},
        )
        with self._lock:
            self.pairing, self.server = pairing, server
            self.connections = {}
            for cid in self.vault.ids():
                self.vault.delete(cid)
            self.vault.keep_sealing_key(private)
        self._wake.set()
        return keys.short(out.get("connectorFingerprint", pairing.fingerprint))

    def unpair(self) -> None:
        """Forget the server and delete every credential held for it (S18.4.4)."""
        with self._lock:
            if self.server:
                try:
                    self.server.call("/connector/v1/unpaired")
                except (ServerError, Exception) as e:
                    log.warning("the server wasn't told of the unpairing: %s", e)
            keys.forget(self.data / "pairing.json")
            self.pairing = self.server = None
            self.connections = {}
            if not self.vault.locked:
                for cid in self.vault.ids():
                    self.vault.delete(cid)

    # ----- the loop -----

    def status(self) -> dict:
        with self._lock:
            return {
                "paired": self.pairing is not None,
                "server": self.pairing.address if self.pairing else None,
                "fingerprint": keys.short(self.pairing.fingerprint) if self.pairing else None,
                "locked": self.vault.locked,
                "vault": self.vault.fingerprint(),
                "lastReport": self.last_report,
                "lastError": self.last_error,
                "connections": {
                    c.id: {
                        "label": c.label,
                        "driver": c.driver,
                        "state": c.state,
                        "message": c.message,
                    }
                    for c in self.connections.values()
                },
            }

    def unlock(self, phrase: str) -> None:
        self.vault.unlock(phrase)
        self._wake.set()

    def connect(self, connection_id: str, credentials: dict) -> None:
        """Credentials typed on this host (S18.7.2), straight into the vault, bound to the host
        the Connection's settings name now (S18.7.3), so the Connection must be known here."""
        with self._lock:
            c = self.connections.get(connection_id)
            if c is None and self.server is not None:
                self.tick()
                c = self.connections.get(connection_id)
            if c is None:
                raise VaultError(
                    "the connector hasn't heard of that Connection yet: check its id, or try "
                    "again after its next report"
                )
            self.vault.put(connection_id, credentials, self._binds(c))
            c.state, c.message, c.last_run = "ok", "credentials received", None
        self._wake.set()

    def _binds(self, c: ConnectionState) -> str | None:
        d = self.drivers.get(c.driver)
        return d.binds(c.settings) if d else None

    def run_forever(self) -> None:
        while not self._stop.is_set():
            try:
                self.tick()
            except Exception as e:  # the loop never dies on one bad report
                self.last_error = f"{type(e).__name__}: {e}"
                log.warning("report failed: %s", e)
            self._wake.wait(REPORT_SECONDS)
            self._wake.clear()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()

    def tick(self) -> None:
        """One round: report, collect, run what is due, post."""
        if self.server is None:
            return
        with self._lock:
            answer = self.server.call("/connector/v1/report", self._report())
            self.last_report, self.last_error = time.time(), None
            self._apply(answer)
            for c in list(self.connections.values()):
                if self._due(c):
                    self._run(c)
            self._post_backlogs()

    def _report(self) -> dict:
        return {
            "locked": self.vault.locked,
            "connections": [
                {
                    "id": c.id,
                    "state": c.state,
                    "message": c.message,
                    "lastRunAt": _iso(c.last_run),
                    "lastRunAdded": c.last_added,
                    "institutionAccounts": c.found,
                    "signInAddress": c.sign_in,
                }
                for c in self.connections.values()
            ],
        }

    def _apply(self, answer: dict) -> None:
        seen = set()
        for rep in answer.get("connections") or []:
            cid = rep["id"]
            seen.add(cid)
            c = self.connections.get(cid)
            if c is None:
                c = self.connections[cid] = ConnectionState(
                    cid, rep.get("driver", ""), rep.get("label", ""), rep.get("settings") or {}, []
                )
            c.settings = rep.get("settings") or c.settings
            c.label = rep.get("label") or c.label
            c.accounts = [
                Account(a["id"], a.get("syncAccount"), a.get("formats") or [])
                for a in rep.get("accounts") or []
            ]
            box = (rep.get("sealed") or {}).get("ciphertext")
            if box and not self.vault.locked:
                self._collect(c, box)
        for cid in answer.get("removed") or []:
            self.connections.pop(cid, None)
            if not self.vault.locked:
                self.vault.delete(cid)
        for cid in list(self.connections):
            if cid not in seen:
                self.connections.pop(cid)

    def _collect(self, c: ConnectionState, box: str) -> None:
        """A sealed credential, opened with the sealing key from the vault and filed bound to
        the host the Connection's settings name now (S18.7.1, S18.7.3)."""
        try:
            creds = sealed.open_box(box, self.vault.sealing_key() or b"", c.id)
        except Exception:
            c.state, c.message = "failing", "the credentials were sealed for another connector"
            return
        self.vault.put(c.id, creds, self._binds(c))
        self.server.call(f"/connector/v1/connections/{c.id}/credential/taken")
        c.state, c.message, c.sign_in, c.last_run = "ok", "credentials received", None, None

    def _due(self, c: ConnectionState) -> bool:
        d = self.drivers.get(c.driver)
        if d is None or (d.needs and self.vault.locked):
            return False
        return c.last_run is None or time.time() - c.last_run >= d.interval

    def _run(self, c: ConnectionState) -> None:
        d = self.drivers[c.driver]
        creds = None
        if d.needs:
            creds = self.vault.get(c.id)
            if creds is None:
                address = d.sign_in(c.settings)
                if address and c.sign_in != address:
                    c.sign_in = address
                    self.server.call(
                        f"/connector/v1/connections/{c.id}/sign-in", {"address": address}
                    )
                c.state, c.message, c.last_run = "new", "waiting for credentials", time.time()
                return
            bound, wanted = self.vault.host(c.id), d.binds(c.settings)
            if bound != wanted:
                # The settings now name another host than the one the credentials were
                # filed for (S18.7.3): nothing is sent until the owner enters them again.
                self.vault.delete(c.id)
                c.state, c.last_run = "needs-sign-in", time.time()
                c.message = (
                    f"the server address changed from {bound or 'none'} to {wanted or 'none'}: "
                    "enter the credentials again"
                )
                return
        try:
            self.egress.allow(*d.hosts_for(c.settings))
            r = d.run(c.settings, creds, c.accounts, self.transport)
        except client.EgressRefused as e:
            c.state, c.message, c.last_run = "failing", f"refused: {e}", time.time()
            return
        except Exception as e:
            c.state, c.message, c.last_run = "failing", f"{type(e).__name__}: {e}", time.time()
            return
        c.state, c.message, c.last_run = r.state, r.message, time.time()
        c.found = r.found or c.found
        c.sign_in = r.sign_in
        if r.credentials is not None:
            self.vault.put(c.id, r.credentials, self.vault.host(c.id))
        if r.sign_in:
            self.server.call(f"/connector/v1/connections/{c.id}/sign-in", {"address": r.sign_in})
        c.backlog.extend(r.files)
        c.last_added = 0

    def _post_backlogs(self) -> None:
        for c in self.connections.values():
            kept: list[File] = []
            for f in c.backlog:
                try:
                    out = self._post(c, f)
                except ServerError as e:
                    if e.code in ("limit", "not-confirmed"):
                        kept.append(f)  # a later run (S18.8), or once an admin confirms
                    else:
                        c.state, c.message = "failing", f"{f.name}: {e.message}"
                    continue
                imported = out.get("imported") or {}
                c.last_added = (c.last_added or 0) + int(imported.get("added") or 0)
            c.backlog = kept
            if c.backlog and c.state == "ok":
                c.message = (
                    f"{len(c.backlog)} waiting: the upload limit, or the pairing's confirmation"
                )

    def _post(self, c: ConnectionState, f: File) -> dict:
        import hashlib

        meta = json.dumps(
            {
                "connectionId": c.id,
                "format": f.fmt,
                "fileName": f.name,
                "sha256": hashlib.sha256(f.data).hexdigest(),
                "fetchedAt": _iso(time.time()),
            }
        ).encode()
        boundary = "mk-connector-" + hashlib.sha256(f.data).hexdigest()[:16]
        body = (
            (
                f'--{boundary}\r\nContent-Disposition: form-data; name="meta"\r\n'
                f"Content-Type: application/json\r\n\r\n"
            ).encode()
            + meta
            + (
                f'\r\n--{boundary}\r\nContent-Disposition: form-data; name="file"; '
                f'filename="{f.name}"\r\nContent-Type: application/octet-stream\r\n\r\n'
            ).encode()
            + f.data
            + f"\r\n--{boundary}--\r\n".encode()
        )
        return self.server.call(
            f"/connector/v1/accounts/{f.account_id}/files",
            body=body,
            ctype=f"multipart/form-data; boundary={boundary}",
        )


def decode_code(code: str) -> dict:
    code = "".join(code.split())
    if not code.startswith("mkp1."):
        raise ServerError("code-invalid", "That isn't a pairing code: it starts mkp1.")
    try:
        out = json.loads(keys.unb64(code[5:]))
        assert isinstance(out, dict) and {"a", "f", "c"} <= set(out)
    except ValueError, AssertionError:
        raise ServerError("code-invalid", "The pairing code is damaged: copy it whole.") from None
    return out


def _host(address: str) -> str:
    from urllib.parse import urlsplit

    return urlsplit(address).hostname or ""


def _iso(t: float | None) -> str | None:
    if t is None:
        return None
    import datetime as dt

    return dt.datetime.fromtimestamp(t, dt.UTC).replace(microsecond=0).isoformat()
