"""Positions (requirements S3.1, S3.9): open and closed, lots' holding periods, and gains
grouped."""

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


def trade(c, acct, day, kind, qty, price, symbol="VTI"):
    amount = float(qty) * float(price)
    add(
        c,
        acct,
        f"{-amount if kind == 'buy' else amount:.2f}",
        day,
        kind=kind,
        symbol=symbol,
        quantity=qty,
        price=price,
    )


def test_open_and_closed_with_their_lots(alice):
    brk = new_account(alice, name="Brokerage", type="brokerage")
    trade(alice, brk["id"], "2024-01-05", "buy", "10", "100")
    trade(alice, brk["id"], "2026-06-01", "buy", "10", "200")
    trade(alice, brk["id"], "2026-08-01", "sell", "5", "220")
    trade(alice, brk["id"], "2025-02-01", "buy", "4", "50", "AAPL")
    trade(alice, brk["id"], "2026-03-01", "sell", "4", "40", "AAPL")
    v = alice.get("/ui/api/positions").json()
    vti = next(r for r in v["open"] if r["symbol"] == "VTI")
    assert vti["quantity"] == "15.0" and vti["term"] == "mixed" and len(vti["lots"]) == 2
    assert vti["cost"] == "2500.00" and vti["realized"] == "600.00"
    assert [x["longTerm"] for x in vti["lots"]] == [True, False]
    closed = {r["symbol"]: r for r in v["closed"]}
    assert closed["AAPL"]["realized"] == "-40.00" and closed["AAPL"]["term"] == "long"
    assert closed["AAPL"]["how"] == "sold"
    assert v["summary"]["realizedThisYear"] == "560.00"
    assert v["summary"]["realizedLong"] == "560.00"
    assert alice.get("/ui/api/positions", params={"kind": "options"}).json()["open"] == []


def test_gains_by_month_account_and_term(alice):
    brk = new_account(alice, name="Brokerage", type="brokerage")
    trade(alice, brk["id"], "2026-01-05", "buy", "10", "100")
    trade(alice, brk["id"], "2026-02-01", "sell", "5", "120")
    trade(alice, brk["id"], "2026-03-01", "sell", "5", "90")
    g = alice.get("/ui/api/positions/gains", params={"by": "month", "year": 2026}).json()
    assert [(x["label"], x["total"]) for x in g["realized"]] == [
        ("March 2026", "-50.00"),
        ("February 2026", "100.00"),
    ]
    t = alice.get("/ui/api/positions/gains", params={"by": "term"}).json()
    assert t["realized"] == [
        {
            "key": "short",
            "label": "Short term",
            "shortTerm": "50.00",
            "longTerm": "0.00",
            "total": "50.00",
        }
    ]


def test_a_wash_sale_moves_the_loss_into_the_replacement_lot(server, alice):
    brk = new_account(alice, name="Brokerage", type="brokerage")
    ira = new_account(alice, name="IRA", type="ira")
    trade(alice, brk["id"], "2025-03-01", "buy", "10", "200", "AAPL")
    trade(alice, brk["id"], "2026-06-01", "sell", "10", "150", "AAPL")  # a 500 loss, long term
    trade(alice, ira["id"], "2026-06-20", "buy", "4", "155", "AAPL")
    v = alice.get("/ui/api/positions").json()
    sale = next(r for r in v["closed"] if r["symbol"] == "AAPL")
    assert sale["realized"] == "-300.00", "200 of the 500 loss disallowed: 4 of 10 replaced"
    held = next(r for r in v["open"] if r["symbol"] == "AAPL")
    assert held["cost"] == "820.00", "620 paid and the 200 disallowed"
    lot = held["lots"][0]
    assert lot["acquiredOn"] == "2025-03-20", "the sold shares' 457 days carried over"
    assert lot["longTerm"]
    # Selling the replacement in the IRA undoes nothing; deleting the buy removes the wash.
    items = alice.get("/ui/api/transactions", params={"account": ira["id"]}).json()["items"]
    buy = items[0]
    r = alice.delete(
        f"/ui/api/transactions/{buy['id']}", headers={"If-Match": f'"{buy["version"]}"'}
    )
    assert r.status_code == 204
    sale = next(r for r in alice.get("/ui/api/positions").json()["closed"] if r["symbol"] == "AAPL")
    assert sale["realized"] == "-500.00"
