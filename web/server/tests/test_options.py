"""Options (requirements S3.2, S3.3): the four trades, short options as negative lots, and
their gains at close or expiry."""

import datetime as dt

import pytest
from conftest import make_user, sign_in
from test_accounts import new_account

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


def opt(
    c,
    acct,
    action,
    day,
    premium,
    contracts="1",
    right="put",
    strike="480",
    expiry="2026-11-20",
    fees="0.65",
    **kw,
):
    r = c.post(
        f"/ui/api/accounts/{acct}/options",
        json={
            "date": day,
            "action": action,
            "underlying": "msft",
            "right": right,
            "strike": strike,
            "expiry": expiry,
            "contracts": contracts,
            "premium": premium,
            "fees": fees,
            **kw,
        },
    )
    return r


def test_a_short_put_is_a_negative_lot_and_realizes_at_close(alice):
    brk = new_account(alice, name="Brokerage", type="brokerage")
    r = opt(alice, brk["id"], "sell-to-open", "2026-09-02", "6.40", contracts="2")
    assert r.status_code == 201, r.text
    t = r.json()
    assert t["amount"] == "1279.35", "2 × 100 × 6.40 less 0.65"
    v = alice.get("/ui/api/positions").json()
    row = v["open"][0]
    assert row["symbol"] == "MSFT 20NOV26 480 P" and row["side"] == "short"
    assert row["quantity"] == "-2" and row["cost"] == "-1279.35"
    r = opt(alice, brk["id"], "buy-to-close", "2026-10-01", "2.10", contracts="2")
    assert r.status_code == 201 and r.json()["amount"] == "-420.65"
    v = alice.get("/ui/api/positions").json()
    assert v["open"] == []
    closed = v["closed"][0]
    assert closed["realized"] == "858.70" and closed["how"] == "bought back"


def test_a_long_call_closes_or_expires(alice):
    brk = new_account(alice, name="Brokerage", type="brokerage")
    opt(
        alice,
        brk["id"],
        "buy-to-open",
        "2026-08-01",
        "3.00",
        right="call",
        strike="500",
        contracts="3",
        fees="0",
    )
    opt(
        alice,
        brk["id"],
        "sell-to-close",
        "2026-09-01",
        "5.00",
        right="call",
        strike="500",
        contracts="1",
        fees="0",
    )
    v = alice.get("/ui/api/positions").json()
    assert v["open"][0]["quantity"] == "2"
    assert v["closed"][0]["realized"] == "200.00"
    too_many = opt(
        alice,
        brk["id"],
        "sell-to-close",
        "2026-09-02",
        "5.00",
        right="call",
        strike="500",
        contracts="5",
    )
    assert too_many.status_code == 422
    assert too_many.json()["errors"][0]["code"] == "nothing-to-close"


def test_option_kinds_go_through_their_own_endpoint(alice):
    brk = new_account(alice, name="Brokerage", type="brokerage")
    r = alice.post(
        "/ui/api/transactions",
        json={
            "accountId": brk["id"],
            "date": "2026-09-01",
            "amount": "100",
            "kind": "sell-to-open",
            "symbol": "MSFT",
            "quantity": "1",
        },
    )
    assert r.status_code == 422 and r.json()["errors"][0]["code"] == "option-kind"
    bad = opt(
        alice, brk["id"], "sell-to-open", "2026-09-02", "1", contracts="1.5", right="straddle"
    )
    assert {e["field"] for e in bad.json()["errors"]} == {"contracts", "right"}
