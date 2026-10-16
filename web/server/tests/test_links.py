"""Linked servers' calls (requirements S11.1.3): every call signed with the sender's link key
over its method, path, body, time and nonce, and the answer signed back."""

import time

import pytest
from linkpair import Wire, make_server

from moneykata import ids
from moneykata.links import client, keys, signing
from moneykata.store.entities.links import Link


def reach(srv, *hosts):
    """Let a server call these hosts, as a link to them would."""
    srv.guard.allow(hosts, hosts)


@pytest.fixture
def pair(tmp_path, monkeypatch):
    a, b = make_server(tmp_path, "a"), make_server(tmp_path, "b")
    wire = Wire()
    urls = wire.add("a", a), wire.add("b", b)
    wire.install(monkeypatch)
    yield a, b, urls, wire
    wire.close()
    a.db.dispose()
    b.db.dispose()


def public(srv) -> bytes:
    with srv.db.tx() as s:
        return keys.public_of(s, srv.keys.secrets)


def link(srv, peer_url, peer_key, state="active", role="inviter") -> str:
    with srv.db.tx() as s:
        row = Link(
            id=ids.new_id("Link"),
            state=state,
            role=role,
            address=peer_url,
            peerKey=keys.b64(peer_key),
        )
        s.add(row)
        return row.id


def test_a_linked_server_answers_a_signed_call_and_signs_its_answer(pair):
    a, b, (url_a, url_b), _ = pair
    reach(a, "b.test")
    ka, kb = public(a), public(b)
    assert ka != kb and len(ka) == 32
    assert public(a) == ka, "made once, then kept"
    link(a, url_b, kb)
    link(b, url_a, ka, role="joiner")
    hi = client.hello(a, url_b)
    assert hi["fingerprint"] == keys.fingerprint(kb) and hi["protocol"] == 1
    out = client.call(a, url_b, kb, "/link/v1/ping")
    assert out["state"] == "active"
    with b.db.read() as s:
        row = s.query(Link).one()
        assert row.lastOkAt is not None and row.peerVersion == a.version


def test_a_call_from_an_unknown_key_or_the_wrong_link_state_is_refused(pair):
    a, b, (url_a, url_b), _ = pair
    reach(a, "b.test")
    kb = public(b)
    with pytest.raises(client.LinkError) as e:
        client.call(a, url_b, kb, "/link/v1/ping")
    assert e.value.code == "not-linked"
    link(b, url_a, public(a), state="ended")
    with pytest.raises(client.LinkError) as e:
        client.call(a, url_b, kb, "/link/v1/ping")
    assert e.value.code == "link-ended"


def test_an_answer_not_signed_by_the_peer_is_refused(pair):
    a, b, (url_a, url_b), _ = pair
    reach(a, "b.test")
    link(b, url_a, public(a))
    stranger = keys.raw_public(signing.Ed25519PrivateKey.generate().public_key())
    with pytest.raises(client.LinkError) as e:
        client.call(a, url_b, stranger, "/link/v1/ping")
    assert e.value.code in ("bad-signature", "not-linked")


def test_signatures_times_and_nonces_are_checked():
    k = signing.Ed25519PrivateKey.generate()
    fp = "f" * 64
    nonces = signing.Nonces()
    s = signing.sign_request(k, "POST", "/link/v1/ping", b"{}", fp)
    h = {key.lower(): v for key, v in s.headers.items()}
    caller = signing.verify_request(h, "POST", "/link/v1/ping", b"{}", fp, nonces)
    assert caller.public == keys.raw_public(k.public_key())
    with pytest.raises(signing.Refused, match="already"):
        signing.verify_request(h, "POST", "/link/v1/ping", b"{}", fp, nonces)
    for body, path, other_fp in (
        (b"{1}", "/link/v1/ping", fp),
        (b"{}", "/link/v1/x", fp),
        (b"{}", "/link/v1/ping", "0" * 64),
    ):
        s = signing.sign_request(k, "POST", "/link/v1/ping", b"{}", fp)
        h = {key.lower(): v for key, v in s.headers.items()}
        with pytest.raises(signing.Refused) as e:
            signing.verify_request(h, "POST", path, body, other_fp, nonces)
        assert e.value.code == "bad-signature"
    old = signing.sign_request(k, "POST", "/p", b"", fp, now=time.time() - 61)
    h = {key.lower(): v for key, v in old.headers.items()}
    with pytest.raises(signing.Refused) as e:
        signing.verify_request(h, "POST", "/p", b"", fp, nonces)
    assert e.value.code == "clock-skew"
    with pytest.raises(signing.Refused) as e:
        signing.verify_request({}, "POST", "/p", b"", fp, nonces)
    assert e.value.code == "unsigned"


def test_a_peer_speaking_another_protocol_is_told_which_this_one_speaks(pair, monkeypatch):
    a, b, (url_a, url_b), _ = pair
    reach(a, "b.test")
    link(b, url_a, public(a))
    monkeypatch.setattr(client, "PROTOCOL", 2)
    with pytest.raises(client.LinkError) as e:
        client.call(a, url_b, public(b), "/link/v1/ping")
    assert e.value.code == "protocol-unsupported" and "speaks link protocol 1" in e.value.message


def test_an_unreachable_peer_says_so(pair):
    a, b, (_, url_b), wire = pair
    reach(a, "b.test")
    wire.down.add("b.test")
    with pytest.raises(client.LinkError) as e:
        client.call(a, url_b, public(b), "/link/v1/ping")
    assert e.value.code == "unreachable"


# ---------- invitations, approval and the directory (S11.1, S11.3, S11.6)

from conftest import make_user  # noqa: E402
from linkpair import admin_of, linked  # noqa: E402


@pytest.fixture
def admins(pair):
    a, b, (url_a, url_b), wire = pair
    ca, cb = admin_of(a, url_a), admin_of(b, url_b)
    yield a, b, ca, cb, wire
    ca.close()
    cb.close()


def links_of(c):
    return c.get("/ui/api/settings/links").json()


def test_an_invitation_is_joined_approved_and_each_side_sees_the_others_users(admins):
    from moneykata.store.entities.education import Person

    a, b, ca, cb, _ = admins
    make_user(a, "alice")
    make_user(b, "carol")
    inv = ca.post("/ui/api/settings/links/invitations")
    assert inv.status_code == 201, inv.text
    code = inv.json()["code"]
    assert code.startswith("mkl1.") and inv.json()["link"]["state"] == "invited"
    joined = cb.post("/ui/api/settings/links/join", json={"code": code})
    assert joined.status_code == 201, joined.text
    assert joined.json()["state"] == "pending"
    assert joined.json()["fingerprint"] == links_of(ca)["fingerprint"]
    req = links_of(ca)["links"][0]
    assert req["state"] == "requested" and req["fingerprint"] == links_of(cb)["fingerprint"]
    # Nothing of either household crosses before the approval (S10.10.1, P5).
    assert req["users"] == [] and links_of(cb)["links"][0]["users"] == []
    with a.db.read() as s:
        assert s.query(Person).filter(Person.name == "Carol").count() == 0
    again = cb.post("/ui/api/settings/links/join", json={"code": code})
    assert again.status_code == 422 and again.json()["code"] in ("code-used", "already-linked")
    r = ca.post(f"/ui/api/settings/links/{req['id']}/approve")
    assert r.status_code == 200 and r.json()["state"] == "active"
    b_side = links_of(cb)["links"][0]
    assert b_side["state"] == "active", "told at once by the approval's exchange"
    assert {u["username"] for u in b_side["users"]} == {"admin", "alice"}
    assert {u["username"] for u in links_of(ca)["links"][0]["users"]} == {"admin", "carol"}
    assert b_side["householdName"]
    # Remote users never sign in, and stay out of Users and Groups.
    assert all(u["username"] != "carol" for u in ca.get("/ui/api/users").json()["items"])


def test_the_directory_follows_the_peers_users(admins):
    _a, b, ca, cb, _ = admins
    a_id, b_id = linked(ca, cb)
    make_user(b, "dave")
    assert ca.post(f"/ui/api/settings/links/{a_id}/pull").status_code == 200
    names = {u["username"] for u in links_of(ca)["links"][0]["users"]}
    assert "dave" in names
    from moneykata.store.entities.users import User

    with b.db.tx() as s:
        s.query(User).filter(User.username == "dave").one().active = False
    ca.post(f"/ui/api/settings/links/{a_id}/pull")
    assert "dave" not in {u["username"] for u in links_of(ca)["links"][0]["users"]}
    with b.db.tx() as s:
        s.query(User).filter(User.username == "dave").one().active = True
    cb.post(f"/ui/api/settings/links/{b_id}/pull")
    assert "dave" in {u["username"] for u in links_of(ca)["links"][0]["users"]}, (
        "an exchange from either side updates both"
    )


def test_a_code_for_another_key_or_a_damaged_code_is_refused(admins):
    _a, _b, ca, cb, _ = admins
    code = ca.post("/ui/api/settings/links/invitations").json()["code"]
    from moneykata.links import manage

    c = manage.decode_code(code)
    forged = manage.encode_code(c["a"], "0" * 64, c["c"])
    r = cb.post("/ui/api/settings/links/join", json={"code": forged})
    assert r.status_code == 422 and r.json()["code"] == "fingerprint-mismatch"
    r = cb.post("/ui/api/settings/links/join", json={"code": "hello"})
    assert r.json()["code"] == "code-invalid"


def test_pausing_stops_exchanges_and_ending_reaches_the_other_side(admins):
    _a, _b, ca, cb, wire = admins
    a_id, b_id = linked(ca, cb)
    assert ca.post(f"/ui/api/settings/links/{a_id}/pause").json()["state"] == "paused"
    out = cb.post(f"/ui/api/settings/links/{b_id}/pull").json()
    assert out["lastError"] and "paused" in out["lastError"]
    assert ca.post(f"/ui/api/settings/links/{a_id}/resume").json()["state"] == "active"
    assert cb.post(f"/ui/api/settings/links/{b_id}/pull").json()["lastError"] is None
    wire.down.add("b.test")
    ended = ca.post(f"/ui/api/settings/links/{a_id}/end").json()
    assert ended["state"] == "ended" and ended["users"] == []
    wire.down.clear()
    cb.post(f"/ui/api/settings/links/{b_id}/pull")
    b_side = links_of(cb)["links"][0]
    assert b_side["state"] == "ended" and b_side["users"] == [], "learnt at its next call"


def test_an_unreachable_peer_is_recorded_on_the_link(admins):
    _a, _b, ca, cb, wire = admins
    a_id, _ = linked(ca, cb)
    wire.down.add("b.test")
    out = ca.post(f"/ui/api/settings/links/{a_id}/pull").json()
    assert out["state"] == "active" and "didn't answer" in out["lastError"]
    assert out["failingSince"]


# ---------- sharing with linked people (S10.3.3, S10.4)

from conftest import sign_in  # noqa: E402


def test_an_item_is_shared_read_only_with_a_linked_servers_people(admins):
    a, b, ca, cb, _ = admins
    make_user(b, "carol")
    a_id, _ = linked(ca, cb)
    make_user(a, "alice")
    alice = sign_in(a, "alice")
    acct = alice.post("/ui/api/accounts", json={"name": "Brokerage", "type": "brokerage"}).json()
    v = alice.get(f"/ui/api/shares/account/{acct['id']}").json()
    peers = v["links"]
    assert len(peers) == 1 and peers[0]["linkId"] == a_id
    carol = next(u for u in peers[0]["users"] if u["displayName"] != "Admin B")
    assert all(u["id"] != carol["id"] for u in v["users"]), "remote people only under their server"
    r = alice.put(f"/ui/api/shares/account/{acct['id']}", json={"users": {carol["id"]: "write"}})
    assert r.status_code == 422 and r.json()["code"] == "read-only"
    r = alice.put(
        f"/ui/api/shares/account/{acct['id']}",
        json={"users": {carol["id"]: "read"}, "receipts": {a_id: True}},
    )
    assert r.status_code == 200, r.text
    after = r.json()["view"]["links"][0]
    assert after["includeReceipts"] is True
    assert next(u for u in after["users"] if u["id"] == carol["id"])["level"] == "read"
    # Ending the link removes the share.
    ca.post(f"/ui/api/settings/links/{a_id}/end")
    v = alice.get(f"/ui/api/shares/account/{acct['id']}").json()
    assert v["links"] == []
    from moneykata.store.entities.sharing import Share

    with a.db.read() as s:
        assert s.query(Share).filter(Share.deleted.is_(False)).count() == 0


# ---------- pulls (S11.3.1, S11.4, S11.9.5)

from test_accounts import add  # noqa: E402

from moneykata.links import copy as lcopy  # noqa: E402
from moneykata.links import copydb  # noqa: E402


def docs_in(srv, link_id):
    o = srv.copies.get(link_id)
    with o.engine.connect() as conn:
        items = {r.id: r for r in conn.execute(copydb.Item.select())}
        docs = {
            (r.itemId, r.path, r.viewer): json.loads(r.body, parse_float=str)
            for r in conn.execute(copydb.Doc.select())
        }
    return items, docs


import json  # noqa: E402


def test_a_shared_account_reaches_the_people_it_names_as_its_screens_show_it(admins):
    a, b, ca, cb, _ = admins
    make_user(b, "carol")
    make_user(b, "dave")
    a_id, b_id = linked(ca, cb)
    make_user(a, "alice")
    alice = sign_in(a, "alice")
    acct = alice.post(
        "/ui/api/accounts", json={"name": "Mom's checking", "type": "checking"}
    ).json()
    add(alice, acct["id"], amount="1200.00", payee="Pension")
    carol_here = next(u for u in links_of(ca)["links"][0]["users"] if u["username"] == "carol")
    alice.put(f"/ui/api/shares/account/{acct['id']}", json={"users": {carol_here["id"]: "read"}})
    # Before B has an access key, it learns only who the item names, not what it is.
    cb.post(f"/ui/api/settings/links/{b_id}/pull")
    carol = sign_in(b, "carol")
    dave = sign_in(b, "dave")
    homes = carol.get("/ui/api/linked").json()["items"]
    assert len(homes) == 1 and homes[0]["items"] == 1 and homes[0]["name"]
    assert dave.get("/ui/api/linked").json()["items"] == [], "dave is named by nothing"
    words = cb.post(f"/ui/api/settings/links/{b_id}/copy-key").json()["words"]
    cb.post(f"/ui/api/settings/links/{b_id}/pull")  # the new copy asks for everything
    st = carol.get(f"/ui/api/linked/{b_id}").json()
    assert st["waiting"] == 1 and st["household"]["locked"]
    r = carol.post(f"/ui/api/linked/{b_id}/unlock", json={"words": " ".join(words)})
    assert r.status_code == 200, r.text
    items, docs = docs_in(b, b_id)
    carol_id = carol.get("/ui/api/session").json()["user"]["id"]
    assert items[acct["id"]].name == "Mom's checking"
    assert json.loads(items[acct["id"]].viewers) == [carol_id]
    detail = docs[(acct["id"], f"/accounts/{acct['id']}", carol_id)]
    assert detail["balance"] == "1200.00"
    txns = docs[(acct["id"], f"/transactions?account={acct['id']}", carol_id)]
    assert [t["payee"] for t in txns["items"]] == ["Pension"]
    assert (acct["id"], "", carol_id) in docs, "its row in the accounts list"
    # The window reads them through the API, only for the people they name.
    rows = carol.get(f"/ui/api/linked/{b_id}/items").json()["items"]
    assert [(r["kind"], r["name"]) for r in rows] == [("account", "Mom's checking")]
    assert rows[0]["row"]["balance"] == "1200.00"
    got = carol.get(f"/ui/api/linked/{b_id}/doc", params={"path": f"/accounts/{acct['id']}"})
    assert got.status_code == 200 and got.json()["balance"] == "1200.00"
    assert carol.get(f"/ui/api/linked/{b_id}/doc", params={"path": "/accounts"}).status_code == 404
    assert dave.get(f"/ui/api/linked/{b_id}/items").status_code == 404
    homes = carol.get("/ui/api/linked").json()["items"]
    assert homes[0]["colour"] == "teal" and not homes[0]["locked"]
    r = carol.put(f"/ui/api/linked/{b_id}/colour", json={"colour": "amber"})
    assert r.json()["household"]["colour"] == "amber"
    carol.post(f"/ui/api/linked/{b_id}/lock")
    assert carol.get(f"/ui/api/linked/{b_id}/items").status_code == 423
    carol.post(f"/ui/api/linked/{b_id}/unlock", json={"words": " ".join(words)})
    # Only what changed travels.
    add(alice, acct["id"], amount="-40.00", payee="Pharmacy")
    ca.post(f"/ui/api/settings/links/{a_id}/pull")  # either side can make the exchange
    items, docs = docs_in(b, b_id)
    assert docs[(acct["id"], f"/accounts/{acct['id']}", carol_id)]["balance"] == "1160.00"
    nothing = a  # the next exchange with nothing new sends no change
    from moneykata.store.entities.links import Link

    with nothing.db.read() as s:
        seq = s.get(Link, a_id).sentSeq
    cb.post(f"/ui/api/settings/links/{b_id}/pull")
    with a.db.read() as s:
        assert s.get(Link, a_id).sentSeq == seq
    # A share removed: the item goes.
    alice.put(f"/ui/api/shares/account/{acct['id']}", json={"users": {carol_here["id"]: "none"}})
    cb.post(f"/ui/api/settings/links/{b_id}/pull")
    items, docs = docs_in(b, b_id)
    assert items == {} and docs == {}
    assert carol.get("/ui/api/linked").json()["items"] == []
    # The link ended: the copy goes.
    ca.post(f"/ui/api/settings/links/{a_id}/end")
    assert not lcopy.folder(b.config.data_dir, b_id).exists()


def test_a_reset_copy_is_pulled_again_in_full(admins):
    a, b, ca, cb, _ = admins
    make_user(b, "carol")
    _a_id, b_id = linked(ca, cb)
    make_user(a, "alice")
    alice = sign_in(a, "alice")
    acct = alice.post("/ui/api/accounts", json={"name": "IRA", "type": "ira"}).json()
    carol_here = next(u for u in links_of(ca)["links"][0]["users"] if u["username"] == "carol")
    alice.put(f"/ui/api/shares/account/{acct['id']}", json={"users": {carol_here["id"]: "read"}})
    cb.post(f"/ui/api/settings/links/{b_id}/copy-key")
    cb.post(f"/ui/api/settings/links/{b_id}/pull")
    cb.post(f"/ui/api/settings/links/{b_id}/reset-copy")
    words = cb.post(f"/ui/api/settings/links/{b_id}/copy-key").json()["words"]
    cb.post(f"/ui/api/settings/links/{b_id}/pull")
    carol = sign_in(b, "carol")
    assert (
        carol.post(f"/ui/api/linked/{b_id}/unlock", json={"words": " ".join(words)}).status_code
        == 200
    )
    items, _ = docs_in(b, b_id)
    assert set(items) == {acct["id"]}


def test_receipts_cross_only_when_included_and_open_through_decryption(admins):
    from test_receipts import png

    a, b, ca, cb, _ = admins
    make_user(b, "carol")
    a_id, b_id = linked(ca, cb)
    make_user(a, "alice")
    alice = sign_in(a, "alice")
    acct = alice.post("/ui/api/accounts", json={"name": "Checking", "type": "checking"}).json()
    t = add(alice, acct["id"], amount="-12.50", payee="Blue Bottle")
    image = png()
    rid = alice.post(
        "/ui/api/receipts", files={"file": ("r.png", image, "application/octet-stream")}
    ).json()["id"]
    alice.post(f"/ui/api/receipts/{rid}/links", json={"transactionId": t["id"]})
    carol_here = next(u for u in links_of(ca)["links"][0]["users"] if u["username"] == "carol")
    words = cb.post(f"/ui/api/settings/links/{b_id}/copy-key").json()["words"]
    alice.put(f"/ui/api/shares/account/{acct['id']}", json={"users": {carol_here["id"]: "read"}})
    cb.post(f"/ui/api/settings/links/{b_id}/pull")
    carol = sign_in(b, "carol")
    carol.post(f"/ui/api/linked/{b_id}/unlock", json={"words": " ".join(words)})
    assert carol.get(f"/ui/api/linked/{b_id}/files").json()["items"] == [], "not included: not sent"
    alice.put(
        f"/ui/api/shares/account/{acct['id']}",
        json={"users": {carol_here["id"]: "read"}, "receipts": {a_id: True}},
    )
    cb.post(f"/ui/api/settings/links/{b_id}/pull")
    files = carol.get(f"/ui/api/linked/{b_id}/files").json()["items"]
    assert len(files) == 1 and files[0]["meta"]["transactionId"] == t["id"]
    sealed_dir = lcopy.folder(b.config.data_dir, b_id) / "receipts"
    on_disk = list(sealed_dir.glob("*.mkr"))
    assert len(on_disk) == 1 and image[:64] not in on_disk[0].read_bytes()
    got = carol.get(f"/ui/api/linked/{b_id}/files/{files[0]['id']}")
    assert got.status_code == 200 and got.content == image
    # Served as a local receipt is (S11.9.6.5, S13.7.7): its type from its bytes, in a sandbox.
    assert got.headers["content-type"] == "image/png"
    assert got.headers["content-security-policy"] == "sandbox"
    assert got.headers["content-disposition"].startswith("inline")
    assert got.headers["x-content-type-options"] == "nosniff"
    assert "no-store" in got.headers["cache-control"]
    # A type the bytes don't bear out is never served, whatever the copy's row says.
    with b.copies.get(b_id).engine.begin() as conn:
        conn.execute(copydb.File.update().values(contentType="text/html"))
    got = carol.get(f"/ui/api/linked/{b_id}/files/{files[0]['id']}")
    assert got.status_code == 415 and got.json()["code"] == "receipt-type"
    # Not included any more: the receipt and its sealed file go.
    alice.put(
        f"/ui/api/shares/account/{acct['id']}",
        json={"users": {carol_here["id"]: "read"}, "receipts": {a_id: False}},
    )
    cb.post(f"/ui/api/settings/links/{b_id}/pull")
    assert carol.get(f"/ui/api/linked/{b_id}/files").json()["items"] == []
    assert list(sealed_dir.glob("*.mkr")) == []


def test_sharing_with_a_linked_server_needs_the_password_again(admins):
    """S13.7.2: a share that sends more across a link, and Include receipts turned on."""
    from conftest import stale

    a, b, ca, cb, _ = admins
    make_user(b, "carol")
    a_id, _b_id = linked(ca, cb)
    make_user(a, "alice")
    alice = sign_in(a, "alice")
    acct = alice.post("/ui/api/accounts", json={"name": "IRA", "type": "ira"}).json()
    carol_here = next(u for u in links_of(ca)["links"][0]["users"] if u["username"] == "carol")
    stale(a)
    share = f"/ui/api/shares/account/{acct['id']}"
    r = alice.put(share, json={"users": {carol_here["id"]: "read"}})
    assert r.status_code == 403 and r.json()["code"] == "reauth-required"
    pw = "a long user passphrase"
    assert alice.post("/ui/api/session/reauth", json={"password": pw}).status_code == 204
    assert alice.put(share, json={"users": {carol_here["id"]: "read"}}).status_code == 200
    stale(a)
    # The same share saved again asks nothing; its receipts turned on do.
    assert alice.put(share, json={"users": {carol_here["id"]: "read"}}).status_code == 200
    r = alice.put(share, json={"users": {carol_here["id"]: "read"}, "receipts": {a_id: True}})
    assert r.status_code == 403 and r.json()["code"] == "reauth-required"


def test_a_linked_receipts_type_comes_from_its_bytes(tmp_path):
    """What a source calls a file never decides how it is shown (S11.9.6.5): a page with a
    script is unknown, a PNG a PNG, once the copy opens what its source sealed; and a thumbnail
    is kept only as an image."""
    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
    from test_receipts import png

    from moneykata.links import changes, sealed

    copy = X25519PrivateKey.generate()
    public = copy.public_key().public_bytes_raw()
    for fid, data, kind in (
        ("Rcpt_a", b"<html><script src=/ui/api/linked/x/files/y></script></html>", None),
        ("Rcpt_b", png(), "image/png"),
    ):
        path = tmp_path / f"{fid}.mkr"
        sealed.write(path, sealed.seal(public, sealed.RECEIPT, "s>r", fid, [data]))
        assert changes._type_of(copy, "s>r", fid, path) == (kind or "application/octet-stream")
        assert changes._type_of(copy, "r>s", fid, path) == "application/octet-stream", (
            "sealed for one direction, it opens for no other"
        )
    assert changes._thumbnail("data:image/webp;base64,AAAA") == "data:image/webp;base64,AAAA"
    for bad in ("javascript:alert(1)", "data:text/html;base64,AAAA", None, 7):
        assert changes._thumbnail(bad) is None


def test_a_share_waiting_for_its_access_key_alerts_the_admins(admins):
    from moneykata import alerts

    a, b, ca, cb, _ = admins
    make_user(b, "carol")
    _a_id, b_id = linked(ca, cb)
    make_user(a, "alice")
    alice = sign_in(a, "alice")
    acct = alice.post("/ui/api/accounts", json={"name": "Checking", "type": "checking"}).json()
    carol_here = next(u for u in links_of(ca)["links"][0]["users"] if u["username"] == "carol")
    alice.put(f"/ui/api/shares/account/{acct['id']}", json={"users": {carol_here["id"]: "read"}})
    cb.post(f"/ui/api/settings/links/{b_id}/pull")
    kinds = {x.kind for x in alerts.evaluate(b)}
    assert "link-key-waiting" in kinds
    cb.post(f"/ui/api/settings/links/{b_id}/copy-key")
    assert "link-key-waiting" not in {x.kind for x in alerts.evaluate(b) if not x.resolvedAt}


# ---------- links, the rest (S11.4, S11.7, S12.13)


def test_a_pause_lasts_its_duration_and_the_peer_isnt_alerted(admins):
    import datetime as dt

    from moneykata import clock
    from moneykata.links import manage

    a, _b, ca, cb, _ = admins
    a_id, b_id = linked(ca, cb)
    r = ca.post(f"/ui/api/settings/links/{a_id}/pause", json={"for": "a week"})
    assert r.json()["code"] == "duration-invalid"
    out = ca.post(f"/ui/api/settings/links/{a_id}/pause", json={"for": "2d"}).json()
    assert out["state"] == "paused" and out["pausedUntil"]
    pulled = cb.post(f"/ui/api/settings/links/{b_id}/pull").json()
    assert "paused" in pulled["lastError"] and pulled["failingSince"] is None, "not alerted"
    assert manage.resume_due(a) == 0
    clock.fix(clock.now() + dt.timedelta(days=2, minutes=1))
    try:
        assert manage.resume_due(a) == 1, "it resumes on its own"
    finally:
        clock.fix(None)
    assert links_of(ca)["links"][0]["state"] == "active"
    # Resume now ends a pause early.
    ca.post(f"/ui/api/settings/links/{a_id}/pause", json={"for": "1d"})
    assert ca.post(f"/ui/api/settings/links/{a_id}/resume").json()["pausedUntil"] is None


def test_a_large_change_arrives_in_parts_oldest_first(admins, monkeypatch):
    from moneykata.links import serve

    a, b, ca, cb, _ = admins
    make_user(b, "carol")
    _a_id, b_id = linked(ca, cb)
    make_user(a, "alice")
    alice = sign_in(a, "alice")
    carol_here = next(u for u in links_of(ca)["links"][0]["users"] if u["username"] == "carol")
    ids_ = []
    for year in (2020, 2023, 2026):
        acct = alice.post(
            "/ui/api/accounts", json={"name": f"Account {year}", "type": "checking"}
        ).json()
        add(alice, acct["id"], amount="10.00", day=f"{year}-03-02", payee="Opening")
        alice.put(
            f"/ui/api/shares/account/{acct['id']}", json={"users": {carol_here["id"]: "read"}}
        )
        ids_.append(acct["id"])
    words = cb.post(f"/ui/api/settings/links/{b_id}/copy-key").json()["words"]
    seen: list[dict] = []
    real = serve.split

    def small(change):
        parts = real(change)
        seen.extend(parts)
        return parts

    monkeypatch.setattr(serve, "PART_BYTES", 2000)
    monkeypatch.setattr(serve, "split", small)
    cb.post(f"/ui/api/settings/links/{b_id}/pull")
    assert len(seen) > 2, "a large change travels in parts"
    throughs = [p["progress"]["through"] for p in seen]
    assert throughs == sorted(throughs), "oldest to newest"
    assert seen[-1]["progress"]["bytes"] == seen[-1]["progress"]["total"]
    side = links_of(cb)["links"][0]
    assert side["syncTotal"] is None, "all of it arrived"
    carol = sign_in(b, "carol")
    carol.post(f"/ui/api/linked/{b_id}/unlock", json={"words": " ".join(words)})
    items, _docs = docs_in(b, b_id)
    assert set(ids_) <= set(items), "every part applied, in order"


def test_a_remote_user_is_a_person_of_their_own_until_someone_joins_them(admins):
    """S10.10.1 (P5): a linked server's user never takes over a person here by its name; one
    who may change that person joins them, and its privacy stays as it was."""
    from moneykata.store.entities.education import Person
    from moneykata.store.entities.users import User

    a, b, ca, cb, _ = admins
    make_user(a, "alice")
    alice = sign_in(a, "alice")
    plan = alice.post(
        "/ui/api/people", json={"name": "Carol", "sex": "female", "private": True}
    ).json()
    make_user(b, "carol")
    linked(ca, cb)
    with a.db.read() as s:
        carol = s.query(User).filter(User.username == "carol", User.linkId.is_not(None)).one()
        assert carol.personId != plan["id"], "not joined by name"
        assert s.get(Person, plan["id"]).private
    row = next(p for p in alice.get("/ui/api/people").json()["items"] if p["id"] == plan["id"])
    assert [r["id"] for r in row["sameAs"]] == [carol.id]
    r = alice.post(f"/ui/api/persons/{plan['id']}/join", json={"userId": carol.id})
    assert r.status_code == 200, r.text
    with a.db.read() as s:
        assert s.get(User, carol.id).personId == plan["id"]
        assert s.get(Person, plan["id"]).private, "joining never changes whether it is private"
    # Exchanges keep the joined person's name as it is here.
    ca.post(f"/ui/api/settings/links/{links_of(ca)['links'][0]['id']}/pull")
    with a.db.read() as s:
        assert s.get(Person, plan["id"]).name == "Carol"


def test_an_answer_names_its_caller_and_its_call():
    """link-protocol.md §3.3: a signed answer handed on to another caller, or to another
    request, is refused."""
    k = signing.Ed25519PrivateKey.generate()
    pub = keys.raw_public(k.public_key())
    asked = signing.Asked("n0nce-n0nce", "a" * 64, signing.body_hash(b"{}"))
    headers = signing.sign_answer(k, 200, b'{"ok":true}', asked)
    signing.verify_answer(pub, 200, b'{"ok":true}', asked, headers)
    for other in (
        signing.Asked("n0nce-n0nce", "b" * 64, asked.body_hash),
        signing.Asked("n0nce-n0nce", asked.caller_fp, signing.body_hash(b'{"x":1}')),
        signing.Asked("another-nonce", asked.caller_fp, asked.body_hash),
    ):
        with pytest.raises(signing.Refused) as e:
            signing.verify_answer(pub, 200, b'{"ok":true}', other, headers)
        assert e.value.code == "bad-signature"


def test_only_link_ended_ends_a_link_and_not_linked_marks_it_broken(admins):
    """S11.6: a peer restored from an older backup answers `not-linked`; the link is marked
    broken and alerts admins, and nothing is deleted."""
    from moneykata import alerts
    from moneykata.links import manage

    a, b, ca, cb, _ = admins
    a_id, _b_id = linked(ca, cb)
    other = keys.b64(keys.raw_public(signing.Ed25519PrivateKey.generate().public_key()))
    with b.db.tx() as s:  # b has no link with a's key, as an older backup wouldn't
        s.query(Link).update({Link.peerKey: other})
    out = ca.post(f"/ui/api/settings/links/{a_id}/pull").json()
    assert out["state"] == "active" and "no link with this one" in out["lastError"]
    with a.db.read() as s:
        assert s.get(Link, a_id).brokenAt is not None
    alerts.evaluate(a)
    assert any(x["kind"] == "link-broken" for x in ca.get("/ui/api/alerts").json()["open"])
    assert manage.pins  # the module is there for what follows


def test_what_crosses_a_link_is_sealed_to_the_receiving_copy(admins, monkeypatch):
    """S11.9.6, link-protocol.md §4.4: in transit, a change shows its registry only; its items'
    names and figures, and its receipts, open only with the receiving copy's key."""
    from test_accounts import add

    a, b, ca, cb, wire = admins
    make_user(b, "carol")
    _a_id, b_id = linked(ca, cb)
    make_user(a, "alice")
    alice = sign_in(a, "alice")
    acct = alice.post("/ui/api/accounts", json={"name": "Secret Brokerage", "type": "brokerage"})
    acct = acct.json()
    add(alice, acct["id"], amount="-1234.56", payee="A very private payee")
    carol_here = next(u for u in links_of(ca)["links"][0]["users"] if u["username"] == "carol")
    words = cb.post(f"/ui/api/settings/links/{b_id}/copy-key").json()["words"]
    alice.put(f"/ui/api/shares/account/{acct['id']}", json={"users": {carol_here["id"]: "read"}})
    seen: list[bytes] = []
    original = wire.client

    def watching(guard=None, **kw):
        c = original(guard, **kw)
        post = c.post

        def spy(url, **k):
            r = post(url, **k)
            seen.append(r.content)
            seen.append(k.get("content") or b"")
            return r

        c.post = spy
        return c

    from moneykata.links import client as link_client

    monkeypatch.setattr(link_client.net, "Client", watching)
    cb.post(f"/ui/api/settings/links/{b_id}/pull")
    wire_bytes = b"".join(x if isinstance(x, bytes) else b"" for x in seen)
    assert b"Secret Brokerage" not in wire_bytes and b"A very private payee" not in wire_bytes
    assert b'"sealed"' in wire_bytes, "the change crossed, sealed"
    carol = sign_in(b, "carol")
    carol.post(f"/ui/api/linked/{b_id}/unlock", json={"words": " ".join(words)})
    items, _ = docs_in(b, b_id)
    assert [i.name for i in items.values()] == ["Secret Brokerage"], "the copy opens it"


def test_a_peers_own_certificate_is_pinned_announced_and_accepted(admins, monkeypatch):
    """link-protocol.md §4.5: an announced key is accepted beside the pinned one and becomes
    the pinned one once in use; one presented unannounced waits for an admin to accept it,
    after the password again."""
    from moneykata.links import client as link_client
    from moneykata.links import manage

    a, _b, ca, cb, _ = admins
    a_id, _ = linked(ca, cb)
    old, new, rogue = "aa" * 32, "bb" * 32, "cc" * 32
    with a.db.tx() as s:
        s.get(Link, a_id).peerCert = old
    with a.db.read() as s:
        assert manage.pins(s.get(Link, a_id)) == {old}
    with a.db.read() as s:
        manage.answer_certificate(a, s.get(Link, a_id), {"fingerprint": new})
    with a.db.read() as s:
        assert manage.pins(s.get(Link, a_id)) == {old, new}
    real = link_client.call

    def over(key):
        def fake(*args, seen=None, **kw):
            out = real(*args, **kw)
            if seen is not None:
                seen.append(key)
            return out

        return fake

    monkeypatch.setattr(link_client, "call", over(new))
    manage.call(a, a_id, "/link/v1/ping")
    with a.db.read() as s:
        row = s.get(Link, a_id)
        assert (row.peerCert, row.peerCertNext) == (new, None), "in use: now the pinned one"

    def refused(*args, **kw):
        raise link_client.LinkError("certificate-changed", "changed", offered=rogue)

    monkeypatch.setattr(link_client, "call", refused)
    with pytest.raises(link_client.LinkError):
        manage.call(a, a_id, "/link/v1/ping")
    shown = next(x for x in links_of(ca)["links"] if x["id"] == a_id)
    assert shown["certificateOffered"] == rogue and shown["certificate"] == keys.short(new)
    r = ca.post(f"/ui/api/settings/links/{a_id}/accept-certificate")
    assert r.status_code == 200 and r.json()["certificate"] == keys.short(rogue)
    assert r.json()["certificateOffered"] is None
