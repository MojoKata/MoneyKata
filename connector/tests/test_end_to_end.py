"""The connector against a real MoneyKata (requirements S18.4–S18.8): paired from a code,
reporting, collecting a credential the owner sealed, running the Folder driver and posting
what it found through the import, a post refused for a limit kept for a later run, and
unpairing. MoneyKata runs in-process; the connector's HTTPS transport is wired to it."""

import json

import pytest
from moneykata_connector import client
from moneykata_connector.core import Core
from moneykata_connector.drivers.folder import Folder
from server_conftest import ORIGIN, make_user, sign_in


class Wired(client.Transport):
    """The connector's requests delivered to MoneyKata's app in-process."""

    def __init__(self, app_client, egress):
        super().__init__(egress)
        self.app = app_client

    def request(self, method, url, headers, body, verify=True):
        from urllib.parse import urlsplit

        u = urlsplit(url)
        self.egress.check(u.hostname or "")
        r = self.app.request(method, u.path, content=body, headers=headers)
        return client.Answer(r.status_code, dict(r.headers), r.content)


@pytest.fixture
def money(server, admin_client, client):
    from moneykata import settings

    with server.db.tx() as s:
        settings.put(s, "publicUrl", ORIGIN, None)
    return server, admin_client, client


def test_the_connector_pairs_reports_collects_and_posts(money, tmp_path):
    from moneykata.connector import sealed as mk_sealed
    from moneykata.links import keys as mk_keys
    from moneykata.store.entities.accounts import Account, Transaction

    server, admin, app = money
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    folder = Folder(tmp_path / "posted.json", root=tmp_path)
    core = Core(tmp_path / "data", transport=None, drivers={"folder": folder})
    core.transport = Wired(app, core.egress)
    phrase = " ".join(core.vault.create())

    # Pair from the code Settings shows, with the vault unlocked (the sealing key goes into
    # it); both sides show the same fingerprint.
    code = admin.post("/ui/api/settings/connector/pairings").json()["code"]
    shown = core.pair(code)
    view = admin.get("/ui/api/settings/connector").json()
    assert view["state"] == "paired" and view["fingerprint"] == shown
    assert "sealingPublic" in (tmp_path / "data" / "pairing.json").read_text()
    # Until an admin confirms the fingerprints match, a posted file waits (S18.4.3).
    assert admin.post("/ui/api/settings/connector/confirm").status_code == 200
    core.vault.lock()
    # A locked connector reports so, and MoneyKata alerts.
    core.tick()
    assert admin.get("/ui/api/settings/connector").json()["locked"] is True

    # Alice makes a folder Connection and syncs her checking account to it.
    alice = make_user(server, "alice").id
    c = sign_in(server, "alice")
    conn = c.post(
        "/ui/api/profile/connections",
        json={
            "driver": "folder",
            "label": "Downloads",
            "settings": {"path": "downloads", "rules": ["umb-*.ofx → 4417"]},
        },
    ).json()["connection"]
    with server.db.tx() as s:
        a = Account(
            id="Acct_01m4zzbtececftrsacpbatewws", ownerId=alice, name="Checking", type="checking"
        )
        s.add(a)
    aid = "Acct_01m4zzbtececftrsacpbatewws"
    v = c.get(f"/ui/api/accounts/{aid}").json()["version"]
    r = c.patch(
        f"/ui/api/accounts/{aid}",
        json={"connectionId": conn["id"], "syncAccount": "Checking ••4417"},
        headers={"If-Match": f'"{v}"'},
    )
    assert r.status_code == 200, r.text
    # A sealed credential for a (pretend) sign-in: collected once unlocked, then gone.
    public = mk_keys.unb64(c.get("/ui/api/connector").json()["sealingKey"])
    box = mk_sealed.seal(b'{"note": "none needed"}', public, conn["id"])
    c.put(f"/ui/api/profile/connections/{conn['id']}/credential", json={"sealed": box})
    core.tick()
    assert core.vault.locked and core.connections[conn["id"]].label == "Downloads"
    assert c.get("/ui/api/profile/connections").json()["items"][0]["credentialWaiting"] is True
    core.unlock(phrase)
    (downloads / "umb-2026-09.ofx").write_bytes(OFX)
    (downloads / "other-bank.ofx").write_bytes(OFX)
    core.tick()
    assert core.vault.get(conn["id"]) == {"note": "none needed"}
    assert c.get("/ui/api/profile/connections").json()["items"][0]["credentialWaiting"] is False
    state = core.connections[conn["id"]]
    assert state.state == "ok" and state.last_added == 2 and "no rule" in state.message
    with server.db.read() as s:
        assert s.query(Transaction).filter_by(accountId=aid).count() == 2
    # The report carries the run; Settings shows it; nothing posted twice.
    core.tick()
    shown = admin.get("/ui/api/settings/connector").json()["connections"][0]
    assert shown["state"] == "ok" and shown["lastRunAt"]
    with server.db.read() as s:
        assert s.query(Transaction).filter_by(accountId=aid).count() == 2

    # The owner's upload limit: the file waits for a later run.
    for _ in range(60):
        server.upload_rate.hit(alice)
    (downloads / "umb-2026-10.ofx").write_bytes(OFX.replace(b"20260912", b"20261002"))
    state.last_run = None
    core.tick()
    assert len(state.backlog) == 1 and "upload limit" in (state.message or "")
    server.upload_rate.clear(alice)
    core.tick()
    assert state.backlog == []

    # Unpair from MoneyKata: the next report is refused and the connector's loop survives.
    admin.post("/ui/api/settings/connector/unpair")
    with pytest.raises(client.ServerError) as e:
        core.tick()
    assert e.value.code == "not-paired"
    core.unpair()
    assert core.pairing is None and core.vault.ids() == []


def test_a_server_that_isnt_the_one_paired_with_gets_nothing(money, tmp_path):
    _server, admin, app = money
    core = Core(tmp_path / "data", transport=None)
    core.transport = Wired(app, core.egress)
    core.vault.create()
    code = admin.post("/ui/api/settings/connector/pairings").json()["code"]
    bad = json.loads(client.unb64(code[5:]))
    bad["f"] = "0" * 64
    from moneykata_connector.keys import b64

    forged = "mkp1." + b64(json.dumps(bad).encode())
    with pytest.raises(client.ServerError) as e:
        core.pair(forged)
    assert e.value.code == "fingerprint-mismatch"
    assert admin.get("/ui/api/settings/connector").json()["state"] == "pairing"


OFX = b"""OFXHEADER:100
DATA:OFXSGML
VERSION:102
SECURITY:NONE
ENCODING:USASCII
CHARSET:1252
COMPRESSION:NONE
OLDFILEUID:NONE
NEWFILEUID:NONE

<OFX><SIGNONMSGSRSV1><SONRS><STATUS><CODE>0<SEVERITY>INFO</STATUS><DTSERVER>20261001
<LANGUAGE>ENG</SONRS></SIGNONMSGSRSV1><BANKMSGSRSV1><STMTTRNRS><TRNUID>1<STATUS><CODE>0
<SEVERITY>INFO</STATUS><STMTRS><CURDEF>USD<BANKACCTFROM><BANKID>101000695<ACCTID>4417
<ACCTTYPE>CHECKING</BANKACCTFROM><BANKTRANLIST><DTSTART>20260901<DTEND>20260930
<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20260912<TRNAMT>-42.37<FITID>f1<NAME>SHELL</STMTTRN>
<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20260915<TRNAMT>2500.00<FITID>f2<NAME>PAYROLL</STMTTRN>
</BANKTRANLIST><LEDGERBAL><BALAMT>3457.63<DTASOF>20260930</LEDGERBAL></STMTRS></STMTTRNRS>
</BANKMSGSRSV1></OFX>
"""
