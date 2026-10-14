"""Charitable giving (requirements S7.9, S8.9): the plan and target, donations of each type,
what is deductible and needs an acknowledgement, shares from a lot, and the donor-advised fund
counted once."""

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
def alice(server, frozen):
    make_user(server, "alice")
    return sign_in(server, "alice")


def org(c, name, **kw):
    r = c.post("/ui/api/giving/organisations", json={"name": name, **kw})
    assert r.status_code == 201, r.text
    return r.json()


def donate(c, **kw):
    r = c.post("/ui/api/giving/donations", json=kw)
    assert r.status_code == 201, r.text
    return r.json()


def test_the_target_pace_and_pledges(alice):
    r = alice.put(
        "/ui/api/giving/plan",
        json={"year": 2026, "percent": "10", "incomeBasis": "gross", "income": "185000"},
    )
    assert r.status_code == 200, r.text
    church = org(
        alice,
        "St. Mark's Parish",
        ein="36-2167053",
        causes=["Faith"],
        pledge="200",
        pledgeEvery="month",
    )
    donate(alice, date="2026-02-01", kind="cash", organisationId=church["id"], amount="2000")
    v = alice.get("/ui/api/giving").json()
    assert v["target"] == "18500.00" and v["given"] == "2000.00"
    assert v["pace"] == str(round(18500 * 286 / 365)) + ".00"
    assert v["pledged"] == "400.00", "November and December"
    assert v["projected"] == "2400.00"
    assert v["byCause"] == [{"label": "Faith", "amount": "2000.00"}]
    bad = alice.put("/ui/api/giving/plan", json={"year": 2026, "incomeBasis": "gross"})
    assert bad.json()["errors"][0]["field"] == "income"


def test_giving_transactions_count_and_acknowledgements_are_flagged(alice):
    alice.put("/ui/api/giving/plan", json={"year": 2026, "percent": "10"})
    org(alice, "Red Cross")
    bank = new_account(alice, name="Checking")
    add(alice, bank["id"], "9000.00", "2026-01-02", categoryId=_cat(alice, "Salary"))
    add(
        alice,
        bank["id"],
        "-300.00",
        "2026-03-01",
        payee="Red Cross",
        categoryId=_cat(alice, "Giving"),
    )
    rows = alice.get("/ui/api/giving/donations").json()
    assert [(d["name"], d["amount"], d["needsAck"], d["id"]) for d in rows] == [
        ("Red Cross", "300.00", True, None)
    ]
    v = alice.get("/ui/api/giving").json()
    assert v["income"] == "9000.00" and v["target"] == "900.00" and v["missingAcks"] == 1
    # Recorded, then acknowledged.
    red = alice.get("/ui/api/giving/organisations").json()[0]
    d = donate(
        alice,
        date="2026-03-01",
        kind="cash",
        organisationId=red["id"],
        transactionId=rows[0]["transactionId"],
    )
    assert d["amount"] == "300.00"
    up = alice.post(
        "/ui/api/receipts", files={"file": ("ack.pdf", b"%PDF-1.4 thank you", "application/pdf")}
    )
    r = alice.post(
        f"/ui/api/giving/donations/{d['id']}/acknowledgement", json={"receiptId": up.json()["id"]}
    )
    assert r.json()["acknowledged"]
    assert alice.get("/ui/api/giving").json()["missingAcks"] == 0
    assert len(alice.get("/ui/api/giving/donations").json()) == 1, "counted once"


def _cat(c, name):
    return next(x["id"] for x in c.get("/ui/api/categories").json() if x["name"] == name)


def test_shares_from_a_lot_without_a_gain(alice):
    brk = new_account(alice, name="Brokerage", type="brokerage")
    add(
        alice,
        brk["id"],
        "-1000.00",
        "2024-01-05",
        kind="buy",
        symbol="VTI",
        quantity="10",
        price="100",
    )
    add(
        alice,
        brk["id"],
        "-3000.00",
        "2026-06-05",
        kind="buy",
        symbol="VTI",
        quantity="10",
        price="300",
    )
    lots = alice.get(f"/ui/api/accounts/{brk['id']}/holdings").json()["holdings"][0]["lots"]
    old, new = lots
    food = org(alice, "Food Depository")
    d = donate(
        alice,
        date="2026-10-01",
        kind="securities",
        organisationId=food["id"],
        fromAccountId=brk["id"],
        lotId=old["lotId"],
        quantity="4",
        amount="1320",
    )
    assert d["longTerm"] and d["basis"] == "400.00" and d["amount"] == "1320.00"
    # Held under a year: the deduction is the basis.
    d2 = donate(
        alice,
        date="2026-10-01",
        kind="securities",
        organisationId=food["id"],
        fromAccountId=brk["id"],
        lotId=new["lotId"],
        quantity="2",
        amount="660",
    )
    assert not d2["longTerm"] and d2["amount"] == "600.00"
    h = alice.get(f"/ui/api/accounts/{brk['id']}/holdings").json()["holdings"][0]
    assert h["quantity"] == "14"
    assert [x["quantity"] for x in h["lots"]] == ["6", "8"]
    too_many = alice.post(
        "/ui/api/giving/donations",
        json={
            "date": "2026-10-02",
            "kind": "securities",
            "organisationId": food["id"],
            "fromAccountId": brk["id"],
            "lotId": old["lotId"],
            "quantity": "60",
            "amount": "1",
        },
    )
    assert too_many.json()["errors"][0]["field"] == "quantity"


def test_a_donor_advised_fund_counts_once(alice):
    alice.put("/ui/api/giving/plan", json={"year": 2026, "targetKind": "amount", "amount": "5000"})
    fund = new_account(alice, name="Giving fund", type="daf", institution="Fidelity Charitable")
    assert alice.get(f"/ui/api/accounts/{fund['id']}").json()["countInNetWorth"] is False
    bank = new_account(alice, name="Checking")
    add(alice, bank["id"], "20000.00", "2026-01-02")
    library = org(alice, "Library Foundation")
    donate(
        alice,
        date="2026-03-01",
        kind="daf-contribution",
        dafAccountId=fund["id"],
        fromAccountId=bank["id"],
        amount="4000",
    )
    g = donate(
        alice,
        date="2026-06-01",
        kind="daf-grant",
        dafAccountId=fund["id"],
        organisationId=library["id"],
        amount="1000",
        granted=True,
    )
    assert not g["deductible"] and not g["counted"]
    v = alice.get("/ui/api/giving").json()
    assert v["given"] == "4000.00"
    assert v["funds"][0]["balance"] == "3000.00" and v["funds"][0]["granted"] == "1000.00"
    alice.put(
        "/ui/api/giving/plan",
        json={"year": 2026, "targetKind": "amount", "amount": "5000", "dafCounted": "granted"},
    )
    assert alice.get("/ui/api/giving").json()["given"] == "1000.00"


def test_qcds_goods_and_what_they_need(alice):
    church = org(alice, "Parish")
    shop = org(alice, "Goodwill")
    campaign = org(alice, "Friends of a candidate", deductible=False)
    q = donate(alice, date="2026-04-01", kind="qcd", organisationId=church["id"], amount="3000")
    assert not q["deductible"] and q["counted"]
    donate(
        alice,
        date="2026-05-01",
        kind="goods",
        organisationId=shop["id"],
        amount="6000",
        description="A piano",
    )
    p = donate(alice, date="2026-05-02", kind="cash", organisationId=campaign["id"], amount="500")
    assert not p["deductible"] and not p["needsAck"]
    notes = alice.get("/ui/api/giving").json()["notes"]
    assert any("Form 8283" in n for n in notes) and any("appraisal" in n for n in notes)
