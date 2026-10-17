"""The locked start (requirements S13.6, S15.4.3): the server comes up with no key anywhere
and answers only what unlocking needs, until the phrase is entered on the unlock page (or by
`keys unlock`, which posts the same way); wrong phrases count toward the lockout."""

import datetime as dt
import os

import pytest
from conftest import LOOPBACK, ORIGIN
from fastapi.testclient import TestClient

from moneykata.app import Server, create_app
from moneykata.keys import phrase
from moneykata.store import maintenance
from moneykata.store.entities.core import Activity


@pytest.fixture
def locked(keyed_config):
    srv = Server(config=keyed_config)
    with TestClient(create_app(srv), base_url=ORIGIN, client=LOOPBACK) as c:
        yield srv, c
    if srv.store is not None:
        srv.tasks.stop()
        srv.reader.stop()
        srv.db.dispose()


def test_a_locked_server_answers_only_what_unlocking_needs(locked):
    _, c = locked
    r = c.get("/healthz")
    assert r.status_code == 503 and r.json()["status"] == "locked"
    for path in ("/ui/api/session", "/mcp", "/link/v1/hello", "/connector/v1/hello"):
        r = c.get(path)
        assert r.status_code == 503 and r.json()["code"] == "locked", path
        assert r.headers["retry-after"] == "30"
    assert c.get("/ui/").status_code == 200 and c.get("/ui/settings").status_code == 200
    assert c.get("/demo").status_code in (200, 404)  # the mockup, when installed
    state = c.get("/ui/api/unlock").json()
    assert state["locked"] is True and state["fingerprint"].startswith("mk-")


def test_the_phrase_unlocks_once_and_wrong_ones_are_counted(locked, master_key):
    srv, c = locked
    headers = {"Origin": ORIGIN}
    r = c.post("/ui/api/unlock", json={"phrase": "not a phrase"}, headers=headers)
    assert r.status_code == 422 and r.json()["code"] == "phrase-invalid"
    other = " ".join(phrase.to_words(os.urandom(16)))
    r = c.post("/ui/api/unlock", json={"phrase": other}, headers=headers)
    assert r.status_code == 403 and r.json()["code"] == "phrase-wrong"
    assert srv.store is None and c.get("/healthz").status_code == 503
    # No Origin: refused before the phrase is even read (S13.7.4).
    assert c.post("/ui/api/unlock", json={"phrase": other}).status_code == 403
    # Something a host command queued while the server was down reaches Activity at unlock.
    maintenance.queue_host_event(srv.config, "key.verified", {"fingerprint": "mk-x"})
    words = " ".join(phrase.to_words(master_key))
    r = c.post("/ui/api/unlock", json={"phrase": words}, headers=headers)
    assert r.status_code == 200 and r.json()["locked"] is False, r.text
    assert srv.store is not None and srv.ready
    assert c.get("/healthz").status_code == 200
    assert c.get("/ui/api/session").status_code == 401  # open, and nobody signed in yet
    r = c.post("/ui/api/unlock", json={"phrase": words}, headers=headers)
    assert r.status_code == 409
    with srv.db.read() as s:
        kinds = [a.kind for a in s.query(Activity)]
    assert "key.verified" in kinds


def test_ten_wrong_phrases_lock_the_unlock_out(locked):
    _, c = locked
    other = " ".join(phrase.to_words(os.urandom(16)))
    for _ in range(10):
        c.post("/ui/api/unlock", json={"phrase": other}, headers={"Origin": ORIGIN})
    r = c.post("/ui/api/unlock", json={"phrase": other}, headers={"Origin": ORIGIN})
    assert r.status_code == 429 and r.headers["retry-after"]


def test_rotation_and_backups_go_over_the_host_socket_only(locked, master_key):
    """Host commands reach the running server over its Unix socket (S13.6); the listener has
    no route for them, whatever address a request claims to come from."""
    from moneykata.host import create_host_app

    srv, c = locked
    host = TestClient(create_host_app(srv), base_url="http://host")
    words = " ".join(phrase.to_words(master_key))
    new = " ".join(phrase.to_words(os.urandom(16)))
    r = host.post("/host/keys/rotate", json={"phrase": new})
    assert r.status_code == 503 and r.json()["code"] == "locked"
    r = host.post("/host/unlock", json={"phrase": words})
    assert r.status_code == 200 and r.json()["locked"] is False, r.text
    old_fp = host.get("/host/unlock").json()["fingerprint"]
    with srv.maintenance_lock:  # the server's own backup task may be running its first copy
        b = maintenance.backup(srv.config, srv.store, dt.datetime(2026, 1, 1, tzinfo=dt.UTC))
    listed = host.get("/host/keys/copies").json()["copies"]
    mine = next(x for x in listed if x["name"] == b.name)
    assert mine["opens"] == "current" and mine["kind"] == "backup"
    r = host.post("/host/keys/rotate", json={"phrase": new, "copies": {b.name: "reencrypt"}})
    assert r.status_code == 200 and r.json()["from"] == old_fp
    assert r.json()["copies"][b.name] == "re-encrypted at the next unlock"
    assert c.get("/ui/api/unlock").json()["fingerprint"] == r.json()["to"] != old_fp
    r = host.post("/host/backup")
    assert r.status_code == 200 and (srv.config.backup_dir / r.json()["name"]).is_dir()
    with srv.db.read() as s:
        kinds = [a.kind for a in s.query(Activity)]
    assert "key.rotated" in kinds and "db.backup" in kinds
    # The listener has none of it: not from loopback, not with a forged forwarding header.
    forged = {"Origin": ORIGIN, "X-Forwarded-For": "127.0.0.1"}
    for path in ("/ui/api/keys/rotate", "/ui/api/keys/copies", "/host/keys/rotate"):
        assert c.post(path, json={"phrase": new}, headers=forged).status_code in (404, 405)


def test_keys_unlock_hands_the_phrase_over_the_socket(locked, master_key):
    """`moneykata keys unlock` against a server serving its host socket (S15.4.2): the socket
    is the server account's alone, and the phrase never crosses the network."""
    import asyncio
    import stat
    import threading

    from hypercorn.asyncio import serve

    from moneykata import host
    from moneykata.keys import cli as keys_cli

    srv, _ = locked
    said: list[str] = []
    assert keys_cli.unlock(srv.config, ask=lambda _: "x", say=said.append) == 1  # not a phrase
    words = " ".join(phrase.to_words(master_key))
    assert keys_cli.unlock(srv.config, ask=lambda _: words, say=said.append) == 1
    assert "no socket" in said[-1]
    stop = threading.Event()
    loop = asyncio.new_event_loop()

    async def until_stopped():
        await asyncio.to_thread(stop.wait)

    hc = host.hypercorn_config(srv.config)
    t = threading.Thread(
        target=lambda: loop.run_until_complete(
            serve(host.create_host_app(srv), hc, shutdown_trigger=until_stopped)
        ),
        daemon=True,
    )
    t.start()
    try:
        for _ in range(100):
            if srv.config.socket_path.exists():
                break
            threading.Event().wait(0.05)
        assert stat.S_IMODE(srv.config.socket_path.stat().st_mode) == 0o600
        assert stat.S_IMODE(srv.config.socket_path.parent.stat().st_mode) == 0o700
        assert keys_cli.unlock(srv.config, ask=lambda _: words, say=said.append) == 0, said
        assert said[-1].startswith("unlocked: mk-") and srv.store is not None
        assert keys_cli._running(srv.config) is True
    finally:
        stop.set()
        t.join(10)


def test_a_scheduled_reencryption_runs_at_the_unlock_before_the_server_serves(locked, master_key):
    """S15.7.2: scheduled, it runs when the phrase is given, the locked screen following its
    progress and /healthz answering re-encrypting, then the server serves under a new key."""
    import time

    from moneykata.store import reencrypt

    srv, c = locked
    maintenance.open_store(srv.config, master_key).db.dispose()  # a database to re-encrypt
    before = srv.config.keyring_path.read_text()
    reencrypt.schedule(srv.config, {}, None, "settings")
    words = " ".join(phrase.to_words(master_key))
    wrong = " ".join(phrase.to_words(os.urandom(16)))
    r = c.post("/ui/api/unlock", json={"phrase": wrong}, headers={"Origin": ORIGIN})
    assert r.status_code == 403, "the phrase is checked before anything starts"
    r = c.post("/ui/api/unlock", json={"phrase": words}, headers={"Origin": ORIGIN})
    assert r.status_code == 200, r.text
    seen = []
    for _ in range(300):
        state = c.get("/ui/api/unlock").json()
        seen.append((state["locked"], state["reencrypting"], c.get("/healthz").json()["status"]))
        if not state["locked"]:
            break
        time.sleep(0.05)
    assert seen[-1][0] is False and c.get("/healthz").status_code == 200
    assert reencrypt.journal(srv.config) is None and reencrypt.report(srv.config)["backup"]
    assert srv.config.keyring_path.read_text() != before
    with srv.db.read() as s:
        assert "keys.reencrypted" in [a.kind for a in s.query(Activity)]


def test_reencryption_is_scheduled_in_settings_never_run_while_serving(server, admin_client):
    """S15.7.2: Settings › Key storage schedules it for the next restart, after the password
    again; until it begins it can be cancelled."""
    from conftest import stale

    from moneykata.store import reencrypt

    stale(server)
    r = admin_client.post("/ui/api/settings/keys/reencrypt", json={"copies": {}})
    assert r.status_code == 403 and r.json()["code"] == "reauth-required"
    admin_client.post("/ui/api/session/reauth", json={"password": "a long admin passphrase"})
    r = admin_client.post("/ui/api/settings/keys/reencrypt", json={"copies": {"x": "bogus"}})
    assert r.status_code == 422
    r = admin_client.post("/ui/api/settings/keys/reencrypt", json={"copies": {}})
    assert r.status_code == 200 and r.json()["scheduled"]["why"] == "settings"
    assert reencrypt.pending(server.config) and not reencrypt.next_keyring(server.config).exists()
    r = admin_client.delete("/ui/api/settings/keys/reencrypt")
    assert r.status_code == 200 and r.json()["scheduled"] is None
    assert not reencrypt.pending(server.config)


def test_removing_a_copy_asks_for_the_phrase_too(server, admin_client, master_key):
    """S16.13, S13.7.2: Remove takes the password again and the recovery phrase, so an admin's
    session alone deletes no backup; a wrong phrase is refused and counted."""
    b = maintenance.backup(server.config, server.store)
    path = f"/ui/api/settings/keys/copies/{b.name}"
    wrong = " ".join(phrase.to_words(os.urandom(16)))
    r = admin_client.request("DELETE", path, json={"phrase": wrong})
    assert r.status_code == 403 and r.json()["code"] == "phrase-wrong"
    assert b.exists()
    words = " ".join(phrase.to_words(master_key))
    r = admin_client.request("DELETE", path, json={"phrase": words})
    assert r.status_code == 200, r.text
    assert not b.exists()
    with server.db.read() as s:
        assert "signin.failed" in [a.kind for a in s.query(Activity)]
