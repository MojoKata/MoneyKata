"""Tax books (requirements S8.14–S8.17): filers who accept, the accounts counted, filings with
their due dates, results and carried figures, documents against those expected, and next
year's book from this one."""

import datetime as dt

import pytest
from conftest import make_user, sign_in
from test_accounts import add, new_account

from moneykata import clock

T0 = dt.datetime(2026, 10, 13, 12, tzinfo=dt.UTC)


@pytest.fixture
def frozen():
    clock.fix(T0)
    yield
    clock.fix(None)


@pytest.fixture
def couple(server, frozen):
    make_user(server, "alice")
    make_user(server, "bob")
    alice, bob = sign_in(server, "alice"), sign_in(server, "bob")
    a_id = alice.get("/ui/api/session").json()["user"]["id"]
    b_id = bob.get("/ui/api/session").json()["user"]["id"]
    pa = alice.get("/ui/api/profile").json()["personId"]
    pb = bob.get("/ui/api/profile").json()["personId"]
    r = alice.post(
        "/ui/api/relationships",
        json={"person1Id": pa, "person2Id": pb, "relation": "spouse", "fromDate": "2009-06-14"},
    )
    assert r.status_code == 201, r.text
    return alice, bob, a_id, b_id


def book(c, year, filers, **kw):
    r = c.post("/ui/api/tax-books", json={"year": year, "filers": filers, **kw})
    assert r.status_code == 201, r.text
    return r.json()


def test_a_joint_book_counts_a_filer_once_they_accept(server, couple):
    alice, bob, a_id, b_id = couple
    new_account(alice, name="Alice's brokerage", type="brokerage")
    new_account(bob, name="Bob's checking")
    b = book(alice, 2026, [a_id, b_id])
    assert b["label"] == "2026 · Alice & Bob (joint)" and not b["filers"][1]["accepted"]
    d = alice.get(f"/ui/api/tax-books/{b['id']}").json()
    assert [a["name"] for a in d["accounts"]] == ["Alice's brokerage"]
    pending = bob.get("/ui/api/tax-books").json()["items"]
    assert pending[0]["level"] == "pending"
    assert bob.get(f"/ui/api/tax-books/{b['id']}").status_code == 404
    assert bob.post(f"/ui/api/tax-books/{b['id']}/accept").json()["level"] == "owner"
    d = bob.get(f"/ui/api/tax-books/{b['id']}").json()
    assert {a["name"] for a in d["accounts"]} == {"Alice's brokerage", "Bob's checking"}
    make_user(server, "carol")
    c_id = sign_in(server, "carol").get("/ui/api/session").json()["user"]["id"]
    r = alice.post("/ui/api/tax-books", json={"year": 2026, "filers": [a_id, c_id]})
    assert r.status_code == 422 and r.json()["errors"][0]["code"] == "not-married"


def test_accounts_left_out_and_added(couple):
    alice, bob, a_id, _ = couple
    mine = new_account(alice, name="Mine", type="brokerage")
    kid = new_account(bob, name="Emma's custodial", type="brokerage")
    bob_id = bob.get("/ui/api/session").json()["user"]["id"]
    bob.put(f"/ui/api/shares/account/{kid['id']}", json={"users": {a_id: "read"}})
    b = book(alice, 2026, [a_id])
    alice.put(f"/ui/api/tax-books/{b['id']}/accounts/{mine['id']}", json={"counted": False})
    d = alice.put(
        f"/ui/api/tax-books/{b['id']}/accounts/{kid['id']}", json={"counted": True}
    ).json()
    assert [a["name"] for a in d["accounts"]] == ["Emma's custodial"]
    assert [a["name"] for a in d["leftOut"]] == ["Mine"]
    assert bob_id


def test_filings_due_dates_overdue_and_results(couple):
    alice, _, a_id, _ = couple
    bank = new_account(alice, name="Checking")
    refund = add(alice, bank["id"], "1240.00", "2026-03-18", payee="IRS TREAS 310")
    last = book(alice, 2025, [a_id])
    r = alice.post(f"/ui/api/tax-books/{last['id']}/filings", json={"form": "Form 1040"})
    f = r.json()["filings"][0]
    assert f["dueDate"] == "2026-04-15" and f["overdue"]
    dash = alice.get("/ui/api/dashboard").json()["attention"]
    assert any(a["text"] == "Federal return for 2025 is past its due date" for a in dash)
    bad = alice.patch(f"/ui/api/filings/{f['id']}", json={"form": "Form 1040", "progress": "filed"})
    assert bad.json()["errors"][0]["field"] == "filedOn"
    r = alice.patch(
        f"/ui/api/filings/{f['id']}",
        json={
            "form": "Form 1040",
            "progress": "accepted",
            "filedOn": "2026-03-02",
            "filingStatus": "Single",
            "sentBy": "e-file",
            "resultKind": "refund",
            "resultAmount": "1240",
            "resultTransactionId": refund["id"],
            "payments": [{"quarter": 1, "dueDate": "2025-04-15", "amount": "1500"}],
            "carried": {"agi": "214380", "totalTax": "31920", "capitalLossLong": "2100"},
        },
    )
    f = r.json()["filings"][0]
    assert not f["overdue"] and f["resultPaid"].startswith("Checking · Mar 18")
    assert f["payments"][0]["amount"] == "1500.00"
    state = alice.post(
        f"/ui/api/tax-books/{last['id']}/filings",
        json={"jurisdiction": "state", "form": "TC-40"},
    )
    assert state.json()["errors"][0]["field"] == "place"
    # This year's book carries last year's figures.
    now = book(alice, 2026, [a_id])
    d = alice.get(f"/ui/api/tax-books/{now['id']}").json()
    assert d["lastYear"][0]["filing"] == "Federal · Form 1040"
    assert d["lastYear"][0]["figures"]["agi"] == "214380.00"
    assert d["federalDue"] == "2027-04-15"


def test_documents_expected_received_and_carried_to_next_year(couple):
    alice, _, a_id, _ = couple
    brk = new_account(alice, name="Brokerage", type="brokerage", institution="Fidelity")
    new_account(alice, name="Mortgage", type="mortgage", institution="Rocket")
    last = book(alice, 2025, [a_id])
    d = alice.get(f"/ui/api/tax-books/{last['id']}").json()
    assert {e["form"] for e in d["expected"]} == {"1099 (composite)", "1098"}
    up = alice.post(
        "/ui/api/receipts", files={"file": ("w2.pdf", b"%PDF-1.4 w2", "application/pdf")}
    )
    alice.post(
        f"/ui/api/tax-books/{last['id']}/documents",
        json={
            "form": "1099 (composite)",
            "issuer": "Fidelity",
            "accountId": brk["id"],
            "receiptId": up.json()["id"],
        },
    )
    d = alice.post(
        f"/ui/api/tax-books/{last['id']}/documents",
        json={"form": "W-2", "issuer": "Acme Corp"},
    ).json()
    composite = next(e for e in d["expected"] if e["form"] == "1099 (composite)")
    assert composite["document"]["fileName"] == "w2.pdf"
    assert [x["form"] for x in d["received"]] == ["W-2"]
    bad = alice.post(
        f"/ui/api/tax-books/{last['id']}/documents", json={"direction": "filed", "form": "Reply"}
    )
    assert bad.json()["errors"][0]["field"] == "filingId"
    # Next year expects last year's W-2 again.
    now = book(alice, 2026, [a_id])
    d = alice.get(f"/ui/api/tax-books/{now['id']}").json()
    w2 = [e for e in d["expected"] if e["form"] == "W-2"]
    assert [(e["issuer"], e["why"], e["document"]) for e in w2] == [
        ("Acme Corp", "Received in 2025", None)
    ]


def test_a_preparer_helps_but_cannot_delete(server, couple):
    alice, _, a_id, _ = couple
    make_user(server, "dave")
    dave = sign_in(server, "dave")
    d_id = dave.get("/ui/api/session").json()["user"]["id"]
    b = book(alice, 2026, [a_id])
    r = alice.put(f"/ui/api/shares/tax-book/{b['id']}", json={"users": {d_id: "write"}})
    assert r.status_code == 200, r.text
    assert dave.post(f"/ui/api/tax-books/{b['id']}/filings", json={}).status_code == 201
    assert dave.delete(f"/ui/api/tax-books/{b['id']}").status_code == 403
