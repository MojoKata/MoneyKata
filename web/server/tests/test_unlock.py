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


def test_rotation_through_the_running_server_is_for_loopback_only(locked, master_key):
    srv, c = locked
    headers = {"Origin": ORIGIN}
    words = " ".join(phrase.to_words(master_key))
    new = " ".join(phrase.to_words(os.urandom(16)))
    r = c.post("/ui/api/keys/rotate", json={"phrase": new}, headers=headers)
    assert r.status_code == 503 and r.json()["code"] == "locked"
    assert c.post("/ui/api/unlock", json={"phrase": words}, headers=headers).status_code == 200
    old_fp = c.get("/ui/api/unlock").json()["fingerprint"]
    with srv.maintenance_lock:  # the server's own backup task may be running its first copy
        b = maintenance.backup(srv.config, srv.store, dt.datetime(2026, 1, 1, tzinfo=dt.UTC))
    listed = c.get("/ui/api/keys/copies").json()["copies"]
    mine = next(x for x in listed if x["name"] == b.name)
    assert mine["opens"] == "current" and mine["kind"] == "backup"
    r = c.post(
        "/ui/api/keys/rotate",
        json={"phrase": new, "copies": {b.name: "rewrap"}},
        headers=headers,
    )
    assert r.status_code == 200 and r.json()["from"] == old_fp
    assert r.json()["copies"][b.name] == "rewrapped"
    assert c.get("/ui/api/unlock").json()["fingerprint"] == r.json()["to"] != old_fp
    with srv.db.read() as s:
        assert "key.rotated" in [a.kind for a in s.query(Activity)]
    # From anywhere but loopback it does not exist.
    far = TestClient(c.app, base_url=ORIGIN, client=("192.168.1.9", 50000))
    r = far.post("/ui/api/keys/rotate", json={"phrase": new}, headers=headers)
    assert r.status_code == 404
