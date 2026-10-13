"""Loans (requirements S1.9)."""

import datetime as dt
from decimal import Decimal as D

import pytest
from conftest import make_user, sign_in
from test_accounts import add, new_account

from moneykata import clock
from moneykata import loans as L

T0 = dt.datetime(2026, 10, 13, 12, tzinfo=dt.UTC)


@pytest.fixture
def frozen():
    clock.fix(T0)
    yield
    clock.fix(None)


def mortgage_terms(**kw):
    return L.Terms(principal=D(300000), start=dt.date(2025, 1, 1), months=360, rate=D(6), **kw)


def test_the_level_payment_and_its_first_split():
    t = mortgage_terms(escrowTax=D(300), escrowInsurance=D(100), pmi=D(90))
    assert L.scheduled_payment(t) == D("1798.65")
    p = L.split_for(t, [], [], dt.date(2025, 2, 1), D("2288.65"))
    assert (p.interest, p.principal, p.escrowTax, p.pmi) == (
        D("1500.00"),
        D("298.65"),
        D(300),
        D(90),
    )
    assert p.overpayment == 0


def test_an_overpayment_pays_it_off_sooner():
    t = mortgage_terms()
    plain, extra = [], []
    for i in range(1, 25):
        d = L.add_months(t.start, i)
        plain.append(L.split_for(t, plain, [], d, D("1798.65")))
        extra.append(L.split_for(t, extra, [], d, D("1798.65") + (D(20000) if i == 12 else 0)))
    assert extra[11].overpayment == D(20000)
    today = dt.date(2027, 1, 15)
    a, _ = L.summary(t, plain, [], today)
    b, _ = L.summary(t, extra, [], today)
    assert b.payoffDate < a.payoffDate and b.interestAhead < a.interestAhead - 30000
    assert a.payoffDate == dt.date(2055, 1, 1)


def test_a_recast_lowers_the_payment_and_keeps_the_end():
    t = mortgage_terms()
    pays = []
    for i in range(1, 13):
        d = L.add_months(t.start, i)
        pays.append(L.split_for(t, pays, [], d, D("1798.65") + (D(50000) if i == 6 else 0)))
    t.recasts = [(dt.date(2025, 12, 15), D(250))]
    s, _ = L.summary(t, pays, [], dt.date(2026, 1, 15))
    assert s.payment < D("1500") and s.payoffDate == dt.date(2055, 1, 1)


def test_an_arm_reset_changes_the_payment():
    t = mortgage_terms(resets=[(dt.date(2030, 1, 1), D("7.5"))])
    _, rows = L.summary(t, [], [], dt.date(2025, 1, 15))
    before = next(r for r in rows if r.date == dt.date(2029, 12, 1))
    after = next(r for r in rows if r.date == dt.date(2030, 2, 1))
    assert after.principal + after.interest > before.principal + before.interest


def test_daily_interest_for_a_car_loan():
    t = L.Terms(
        principal=D(25000), start=dt.date(2026, 1, 15), months=60, rate=D("7.3"), method="daily"
    )
    p = L.split_for(t, [], [], dt.date(2026, 2, 15), D("500"))
    assert p.interest == (D(25000) * D("0.073") * 31 / 365).quantize(D("0.01"))


def test_a_heloc_pays_interest_only_while_drawing():
    t = L.Terms(principal=D(0), start=dt.date(2026, 1, 1), months=240, rate=D(8), drawMonths=120)
    draws = [(dt.date(2026, 2, 1), D(30000))]
    _, rows = L.summary(t, [], draws, dt.date(2026, 3, 15))
    assert rows[0].principal == 0 and rows[0].interest == D("200.00")
    late = next(r for r in rows if r.date == dt.date(2036, 2, 1))
    assert late.principal > 0


def test_payments_through_the_api(server, frozen):
    make_user(server, "alice")
    c = sign_in(server, "alice")
    bank = new_account(c, name="Checking")
    add(c, bank["id"], "10000.00", "2026-09-01")
    loan = new_account(c, name="Home", type="mortgage", institution="Rocket")
    r = c.put(
        f"/ui/api/accounts/{loan['id']}/loan",
        json={
            "principal": "300000",
            "startDate": "2026-01-01",
            "termMonths": 360,
            "rate": "6",
            "escrowTax": "300",
            "escrowInsurance": "100",
        },
    )
    assert r.status_code == 200, r.text
    v = r.json()
    assert v["terms"]["computedPayment"] == "1798.65" and v["balance"] == "300000.00"
    # A payment from the checking account: both halves, split by the schedule.
    r = c.post(
        f"/ui/api/accounts/{loan['id']}/loan/payments",
        json={"date": "2026-02-01", "amount": "2198.65", "fromAccountId": bank["id"]},
    )
    assert r.status_code == 201, r.text
    v = r.json()
    assert v["balance"] == "299701.35" and v["interestPaid"] == "1500.00"
    # The loan counts in net worth as what is owed.
    acct = c.get(f"/ui/api/accounts/{loan['id']}").json()
    assert acct["balance"] == "-299701.35"
    assert c.get(f"/ui/api/accounts/{bank['id']}").json()["balance"] == "7801.35"
    # A bank transaction that looks like the payment is offered, and linked.
    t = add(c, bank["id"], "-2198.65", "2026-10-01", payee="ROCKET MORTGAGE")
    cands = c.get(f"/ui/api/accounts/{loan['id']}/loan/candidates").json()
    assert [x["transactionId"] for x in cands] == [t["id"]]
    r = c.post(
        f"/ui/api/accounts/{loan['id']}/loan/payments",
        json={"date": "2026-10-01", "amount": "2198.65", "transactionId": t["id"]},
    )
    assert r.status_code == 201
    assert c.get(f"/ui/api/accounts/{loan['id']}/loan/candidates").json() == []
    # A split typed from the servicer's statement must add up.
    r = c.post(
        f"/ui/api/accounts/{loan['id']}/loan/payments",
        json={"date": "2026-11-01", "amount": "2198.65", "principal": "10", "interest": "10"},
    )
    assert r.status_code == 422 and r.json()["errors"][0]["code"] == "split-does-not-add-up"


def test_the_servicers_balance_against_the_computed_one(server, frozen):
    make_user(server, "alice")
    c = sign_in(server, "alice")
    loan = new_account(c, name="Car", type="auto-loan")
    c.put(
        f"/ui/api/accounts/{loan['id']}/loan",
        json={"principal": "20000", "startDate": "2026-01-01", "termMonths": 60, "rate": "5"},
    )
    r = c.post(
        f"/ui/api/accounts/{loan['id']}/anchors",
        json={"date": "2026-10-01", "balance": "-19950.00"},
    )
    assert r.status_code == 201
    v = c.get(f"/ui/api/accounts/{loan['id']}/loan").json()
    assert v["servicer"]["difference"] == "-50.00"


def test_terms_are_checked(server, frozen):
    make_user(server, "alice")
    c = sign_in(server, "alice")
    loan = new_account(c, name="Car", type="auto-loan")
    r = c.put(
        f"/ui/api/accounts/{loan['id']}/loan",
        json={"principal": "-1", "startDate": "2026-01-01", "termMonths": 0, "rate": "99"},
    )
    assert {e["field"] for e in r.json()["errors"]} == {"principal", "termMonths", "rate"}
