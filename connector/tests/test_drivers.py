"""The drivers (requirements S18.9): OFX Direct Connect and Schwab against mocks of their
institutions, the Folder driver against a folder, and what each sends: files MoneyKata's
importer reads, for the accounts whose sync names the Connection."""

import datetime as dt
import json
import time
from urllib.parse import parse_qs, urlsplit

import pytest
from moneykata_connector import client
from moneykata_connector.drivers import Account, registry
from moneykata_connector.drivers.folder import Folder, parse_rules
from moneykata_connector.drivers.ofx_direct import OfxDirect, request
from moneykata_connector.drivers.schwab import Schwab, to_ofx


class Fake(client.Transport):
    """An institution answering by path, recording what it was asked."""

    def __init__(self, answers):
        super().__init__(client.Egress())
        self.answers = answers
        self.calls = []

    def request(self, method, url, headers, body, pins=None):
        u = urlsplit(url)
        self.egress.check(u.hostname or "")
        self.calls.append((method, url, headers, body))
        status, reply = self.answers(method, u, headers, body)
        return client.Answer(
            status, {}, reply if isinstance(reply, bytes) else json.dumps(reply).encode()
        )


OFX_OK = b"".join(
    [
        b"OFXHEADER:100\r\nDATA:OFXSGML\r\nVERSION:102\r\nSECURITY:NONE\r\nENCODING:USASCII\r\nCHARSET:1252\r\nCOMPRESSION:NONE\r\nOLDFILEUID:NONE\r\nNEWFILEUID:NONE\r\n\r\n<OFX><SIGNONMSGSRSV1><SONRS><STATUS><CODE>0<SEVERITY>INFO</STATUS>",
        b"<DTSERVER>20261001<LANGUAGE>ENG</SONRS></SIGNONMSGSRSV1><BANKMSGSRSV1><STMTTRNRS><TRNUID>1<STATUS><CODE>0<SEVERITY>INFO</STATUS>",
        b"<STMTRS><CURDEF>USD<BANKACCTFROM><BANKID>101000695<ACCTID>00001204<ACCTTYPE>CHECKING</BANKACCTFROM><BANKTRANLIST><DTSTART>20260901<DTEND>20260930<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20260912<TRNAMT>-42.37<FITID>f1<NAME>SHELL</STMTTRN></BANKTRANLIST><LEDGERBAL><BALAMT>3457.63<DTASOF>20260930</LEDGERBAL></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>",
    ]
)
OFX_BAD = OFX_OK.replace(b"<SONRS><STATUS><CODE>0", b"<SONRS><STATUS><CODE>15500")


def test_the_ofx_request_names_the_account_and_signs_in():
    settings = {
        "url": "https://ofx.cu.example/ofx",
        "org": "CU",
        "fid": "1204",
        "accountType": "CHECKING",
        "accountId": "00001204",
        "bankId": "101000695",
    }
    body = request(settings, {"username": "alice", "password": "pw"}, dt.date(2026, 9, 1)).decode()
    assert body.startswith("OFXHEADER:100") and "<USERID>alice<USERPASS>pw" in body
    assert "<BANKID>101000695<ACCTID>00001204<ACCTTYPE>CHECKING" in body
    assert "<DTSTART>20260901" in body and "<ORG>CU<FID>1204" in body
    card = request({**settings, "accountType": "CREDITCARD"}, {}, dt.date(2026, 9, 1)).decode()
    assert "<CCSTMTRQ><CCACCTFROM><ACCTID>00001204" in card
    inv = request({**settings, "accountType": "INVESTMENT"}, {}, dt.date(2026, 9, 1)).decode()
    assert (
        "<INVSTMTRQ><INVACCTFROM><BROKERID>101000695<ACCTID>00001204" in inv and "<INCPOS>" in inv
    )


def test_ofx_direct_posts_the_statement_to_the_account_with_those_last_four():
    settings = {
        "url": "https://ofx.cu.example/ofx",
        "org": "CU",
        "fid": "1204",
        "accountType": "CHECKING",
        "accountId": "00001204",
        "bankId": "101000695",
    }
    good = Fake(lambda m, u, h, b: (200, OFX_OK) if b"<USERPASS>pw" in b else (200, OFX_BAD))
    good.egress.allow("ofx.cu.example")
    d = OfxDirect()
    assert d.hosts_for(settings) == ("ofx.cu.example",)
    accounts = [
        Account("Acct_1", "Everyday ••1204", ["ofx"]),
        Account("Acct_2", "Other ••9999", []),
    ]
    r = d.run(settings, {"username": "alice", "password": "pw"}, accounts, good)
    assert r.state == "ok" and [f.account_id for f in r.files] == ["Acct_1"]
    assert r.files[0].data == OFX_OK and r.files[0].fmt == "ofx"
    assert r.found == [{"name": "Checking", "last4": "1204"}]
    assert good.calls[0][2]["Content-Type"] == "application/x-ofx"
    r = d.run(settings, {"username": "alice", "password": "wrong"}, accounts, good)
    assert r.state == "needs-sign-in" and r.files == []
    assert d.run({**settings, "url": "http://plain"}, {}, accounts, good).state == "failing"
    # Another host than the one named is refused by the allowlist.
    strict = Fake(lambda *a: (200, OFX_OK))
    with pytest.raises(client.EgressRefused):
        d.run({**settings, "url": "https://elsewhere.example/ofx"}, {}, accounts, strict)


SCHWAB_ACCOUNT = {
    "securitiesAccount": {
        "accountNumber": "12344417",
        "type": "MARGIN",
        "positions": [
            {
                "instrument": {
                    "symbol": "VTI",
                    "cusip": "922908769",
                    "assetType": "ETF",
                    "description": "Vanguard Total Stock Market ETF",
                },
                "longQuantity": 10.5,
                "shortQuantity": 0,
                "averagePrice": 250.1,
                "marketValue": 2888.75,
            }
        ],
        "currentBalances": {"cashBalance": 1200.5, "liquidationValue": 4089.25},
    }
}
SCHWAB_TXNS = [
    {
        "activityId": 9001,
        "time": "2026-09-12T14:03:00+0000",
        "type": "TRADE",
        "description": "BUY TRADE",
        "netAmount": -1251.0,
        "transferItems": [
            {
                "instrument": {"symbol": "VTI", "cusip": "922908769", "assetType": "ETF"},
                "amount": 5,
                "price": 250.2,
                "cost": -1251.0,
            },
            {"instrument": {"assetType": "CURRENCY", "symbol": "USD"}, "amount": 1251.0},
        ],
    },
    {
        "activityId": 9002,
        "time": "2026-09-20T09:00:00+0000",
        "type": "DIVIDEND_OR_INTEREST",
        "description": "QUALIFIED DIVIDEND (VTI)",
        "netAmount": 8.12,
        "transferItems": [
            {"instrument": {"symbol": "VTI", "cusip": "922908769", "assetType": "ETF"}, "amount": 0}
        ],
    },
    {
        "activityId": 9003,
        "time": "2026-09-25T09:00:00+0000",
        "type": "ELECTRONIC_FUND",
        "description": "ACH deposit",
        "netAmount": 500.0,
        "transferItems": [
            {"instrument": {"assetType": "CURRENCY", "symbol": "USD"}, "amount": 500.0}
        ],
    },
]


def schwab_answers(expired_refresh=False):
    def answer(method, u, headers, body):
        if u.path == "/v1/oauth/token":
            form = parse_qs(body.decode())
            if form.get("grant_type") == ["refresh_token"] and expired_refresh:
                return 401, {"error": "invalid_grant"}
            if form.get("grant_type") == ["authorization_code"] and form.get("code") != ["abc"]:
                return 400, {"error": "invalid_grant"}
            return 200, {"access_token": "at-1", "refresh_token": "rt-1", "expires_in": 1800}
        if headers.get("Authorization") != "Bearer at-1":
            return 401, {}
        if u.path == "/trader/v1/accounts/accountNumbers":
            return 200, [{"accountNumber": "12344417", "hashValue": "HASH1"}]
        if u.path == "/trader/v1/accounts":
            return 200, [SCHWAB_ACCOUNT]
        if u.path == "/trader/v1/accounts/HASH1/transactions":
            return 200, SCHWAB_TXNS
        return 404, {}

    return answer


def test_schwab_signs_in_from_the_landed_address_keeps_the_refresh_token_and_posts_ofx():
    d = Schwab()
    assert d.sign_in({"appKey": "KEY"}).startswith(
        "https://api.schwabapi.com/v1/oauth/authorize?client_id=KEY"
    )
    http = Fake(schwab_answers())
    http.egress.allow(*d.hosts)
    accounts = [
        Account("Acct_1", "Individual ••4417", ["ofx"]),
        Account("Acct_2", "IRA ••0921", []),
    ]
    r = d.run(
        {"appKey": "KEY"},
        {"appSecret": "SECRET", "landed": "https://127.0.0.1/?code=abc&session=x"},
        accounts,
        http,
    )
    assert r.state == "ok", r.message
    assert r.credentials["refreshToken"] == "rt-1" and r.credentials["appSecret"] == "SECRET"
    assert r.credentials["refreshUntil"] > time.time() + 6 * 86400
    assert r.found == [{"name": "Margin", "last4": "4417"}]
    assert [f.account_id for f in r.files] == ["Acct_1"] and r.files[0].fmt == "ofx"
    token_call = http.calls[0]
    assert token_call[2]["Authorization"].startswith("Basic ") and b"code=abc" in token_call[3]
    # MoneyKata's own importer reads what was made: positions, the trade, the dividend, cash.
    from moneykata.importers import ofx as mk_ofx

    parsed = mk_ofx.read(r.files[0].data)
    assert parsed.accountKind == "investment" and parsed.accountNumber == "12344417"
    kinds = sorted(row.kind for row in parsed.rows)
    assert kinds == ["buy", "dividend", "transfer"], kinds
    buy = next(row for row in parsed.rows if row.kind == "buy")
    assert str(buy.quantity) == "5" and str(buy.price) == "250.2" and buy.security == "922908769"
    assert parsed.securities["922908769"].symbol == "VTI"
    assert len(parsed.positions) == 1 and str(parsed.positions[0].quantity) == "10.5"
    assert parsed.balances and str(parsed.balances[0][1]) == "1200.5"
    # A second run uses the access token; past its life, the refresh token; past seven days,
    # the owner must sign in again, at the address reported.
    http.calls.clear()
    r2 = d.run({"appKey": "KEY"}, r.credentials, accounts, http)
    assert r2.state == "ok" and http.calls[0][1].endswith("/accounts/accountNumbers")
    expired = {**r.credentials, "accessUntil": 0, "refreshUntil": 0}
    r3 = d.run({"appKey": "KEY"}, expired, accounts, http)
    assert r3.state == "needs-sign-in" and "authorize" in r3.sign_in
    stale = Fake(schwab_answers(expired_refresh=True))
    stale.egress.allow(*d.hosts)
    r4 = d.run({"appKey": "KEY"}, {**r.credentials, "accessUntil": 0}, accounts, stale)
    assert r4.state == "needs-sign-in"


def test_schwab_ofx_names_every_security_once():
    data = to_ofx(
        SCHWAB_ACCOUNT["securitiesAccount"], SCHWAB_TXNS, dt.datetime(2026, 10, 1, tzinfo=dt.UTC)
    )
    text = data.decode()
    assert text.count("<STOCKINFO>") == 1 and "<TICKER>VTI" in text
    assert "<BUYSTOCK>" in text and "<INCOME>" in text and "<INVBANKTRAN>" in text
    assert "<DTSTART>20260912120000" in text


def test_the_folder_driver_posts_matching_files_once(tmp_path):
    folder = tmp_path / "downloads"
    folder.mkdir()
    (folder / "umb-2026-09.pdf").write_bytes(b"%PDF-1.4 x")
    (folder / "umb-2026-09.ofx").write_bytes(b"OFXHEADER:100")
    (folder / "notes.txt").write_bytes(b"x")
    (folder / "chase.csv").write_bytes(b"a,b")
    d = Folder(tmp_path / "posted.json", root=tmp_path)
    assert parse_rules(["umb-*.pdf → 3311", "umb-*.ofx -> 3311", "bad rule"]) == [
        ("umb-*.pdf", "3311"),
        ("umb-*.ofx", "3311"),
    ]
    accounts = [Account("Acct_1", "Joint ••3311", ["ofx", "statement"])]
    r = d.run(
        {"path": "downloads", "rules": ["umb-*.pdf → 3311", "umb-*.ofx → 3311"]},
        None,
        accounts,
        None,
    )
    assert r.state == "ok" and sorted(f.name for f in r.files) == [
        "umb-2026-09.ofx",
        "umb-2026-09.pdf",
    ]
    assert {f.fmt for f in r.files} == {"ofx", "statement"} and "1 file with no rule" in r.message
    again = Folder(tmp_path / "posted.json", root=tmp_path)
    assert (
        again.run({"path": "downloads", "rules": ["umb-*.pdf → 3311"]}, None, accounts, None).files
        == []
    )
    assert d.run({"path": "nope", "rules": []}, None, accounts, None).state == "failing"
    # An empty path is the watched folder itself.
    assert d.run({"path": "", "rules": []}, None, accounts, None).state == "ok"


def test_the_folder_driver_never_leaves_its_watched_folder(tmp_path):
    """S18.9.1: MoneyKata names a folder inside the mount, never the connector's own files."""
    root = tmp_path / "watch"
    root.mkdir()
    (tmp_path / "secret.ofx").write_bytes(b"OFXHEADER:100")
    (root / "out").symlink_to(tmp_path)
    d = Folder(root=root)
    accounts = [Account("Acct_1", "Joint ••3311", ["ofx"])]
    for path in (str(tmp_path), "../", "a/../../", "/", "out", "out/x"):
        r = d.run({"path": path, "rules": ["* → 3311"]}, None, accounts, None)
        assert r.state == "failing" and "inside the connector's watched folder" in r.message, path
    assert d.inside("") == root.resolve() and d.inside("sub") == (root / "sub").resolve()


def test_every_driver_is_registered_with_its_limits():
    names = set(registry())
    assert names == {"folder", "ofx-direct", "schwab"}
