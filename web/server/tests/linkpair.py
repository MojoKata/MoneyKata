"""Two MoneyKata servers in one test, their link calls wired to each other's app."""

import dataclasses
from urllib.parse import urlsplit

import httpx
from fastapi.testclient import TestClient

from moneykata.app import Server, create_app
from moneykata.auth import users as accounts
from moneykata.config import Config
from moneykata.keys import cli as keys_cli
from moneykata.links import client as link_client
from moneykata.store.maintenance import open_store
from moneykata.store.repos.ledger import ensure_categories


def make_server(tmp_path, name: str) -> Server:
    cfg = Config(
        name=name,
        mode="proxy",
        data_dir=tmp_path / name / "data",
        backup_dir=tmp_path / name / "backups",
        key_file=tmp_path / name / "keys" / "master.key",
    )
    keys_cli.init(cfg, say=lambda _: None, confirm=False)
    srv = Server(config=cfg, store=open_store(cfg), ready=True)
    with srv.db.tx() as s:
        accounts.ensure_default_admin(s)
        ensure_categories(s)
    return srv


class Wire:
    """Routes https://<name>.test/... to that server's app, as the network would."""

    def __init__(self):
        self.apps: dict[str, TestClient] = {}
        self.down: set[str] = set()

    def add(self, name: str, srv: Server) -> str:
        self.apps[f"{name}.test"] = TestClient(
            create_app(srv), base_url=f"https://{name}.test", client=("127.0.0.1", 50000)
        )
        return f"https://{name}.test"

    def client(self, guard=None, **kw):
        wire = self

        class C:
            def _go(self, method, url, **kw):
                host = urlsplit(url).hostname
                if guard is not None:
                    guard.check(host, 443)  # as the real transport does
                if host in wire.down or host not in wire.apps:
                    raise httpx.ConnectError("unreachable")
                return wire.apps[host].request(method, url, **kw)

            def get(self, url, **kw):
                return self._go("GET", url, **kw)

            def post(self, url, **kw):
                return self._go("POST", url, **kw)

            def stream(self, method, url, **kw):
                host = urlsplit(url).hostname
                if guard is not None:
                    guard.check(host, 443)
                if host in wire.down or host not in wire.apps:
                    raise httpx.ConnectError("unreachable")
                return wire.apps[host].stream(method, url, **kw)

        return C()

    def install(self, monkeypatch):
        monkeypatch.setattr(link_client.net, "Client", self.client)

    def close(self):
        for c in self.apps.values():
            c.close()


def with_config(srv: Server, **kw) -> None:
    srv.config = dataclasses.replace(srv.config, **kw)


def admin_of(srv: Server, base: str) -> TestClient:
    """An admin signed in on that server's own UI (its setup step done)."""
    from moneykata import settings

    with srv.db.tx() as s:
        settings.put(s, "publicUrl", base, None)
    c = TestClient(
        create_app(srv), base_url=base, headers={"Origin": base}, client=("127.0.0.1", 50000)
    )
    r = c.post("/ui/api/session", json={"login": "admin", "password": "moneykata-setup"})
    assert r.status_code == 200, r.text
    r = c.post(
        "/ui/api/session/setup",
        json={
            "password": "a long admin passphrase",
            "email": f"admin@{urlsplit(base).hostname}",
            "displayName": f"Admin {urlsplit(base).hostname[0].upper()}",
        },
    )
    assert r.status_code == 200, r.text
    return c


def linked(a_admin: TestClient, b_admin: TestClient) -> tuple[str, str]:
    """A link made the way admins make it: invited on A, joined on B, approved on A."""
    code = a_admin.post("/ui/api/settings/links/invitations").json()["code"]
    b_link = b_admin.post("/ui/api/settings/links/join", json={"code": code})
    assert b_link.status_code == 201, b_link.text
    a_link = next(
        x
        for x in a_admin.get("/ui/api/settings/links").json()["links"]
        if x["state"] == "requested"
    )
    r = a_admin.post(f"/ui/api/settings/links/{a_link['id']}/approve")
    assert r.status_code == 200, r.text
    return a_link["id"], b_link.json()["id"]
