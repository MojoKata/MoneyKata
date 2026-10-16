"""Golden files (requirements S17.5): a fixture portfolio whose Form 8949 rows and TXF file are
known, checked byte for byte. A change to either export shows here as a diff to read; after
reading it, `MK_GOLDEN_WRITE=1 pytest tests/test_golden.py` writes the files again."""

import datetime as dt
import os
from decimal import Decimal
from pathlib import Path

import pytest
from conftest import make_user, sign_in
from test_accounts import add, new_account

from moneykata import clock

GOLDEN = Path(__file__).parent / "golden"
T0 = dt.datetime(2026, 12, 20, 12, tzinfo=dt.UTC)


@pytest.fixture
def alice(server):
    clock.fix(T0)
    make_user(server, "alice", born=1970)
    yield sign_in(server, "alice")
    clock.fix(None)


def trade(c, acct, day, kind, qty, price, symbol):
    amount = Decimal(qty) * Decimal(price)
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


def portfolio(c) -> str:
    brk = new_account(c, name="Taxable", type="brokerage", mask="1001")
    trade(c, brk["id"], "2024-01-05", "buy", "10", "100", "VTI")
    trade(c, brk["id"], "2026-02-01", "sell", "4", "150", "VTI")  # long-term, box D
    trade(c, brk["id"], "2026-03-02", "buy", "10", "400", "MSFT")
    trade(c, brk["id"], "2026-04-01", "sell", "10", "350", "MSFT")  # a loss, washed
    trade(c, brk["id"], "2026-04-15", "buy", "10", "360", "MSFT")  # its replacement
    r = c.post(
        f"/ui/api/accounts/{brk['id']}/options",
        json={
            "date": "2026-05-01",
            "action": "sell-to-open",
            "underlying": "AAPL",
            "right": "put",
            "strike": "200",
            "expiry": "2026-06-19",
            "contracts": "1",
            "premium": "3.10",
            "fees": "0.65",
        },
    )
    assert r.status_code == 201, r.text
    r = c.post(
        f"/ui/api/accounts/{brk['id']}/options",
        json={
            "date": "2026-05-20",
            "action": "buy-to-close",
            "underlying": "AAPL",
            "right": "put",
            "strike": "200",
            "expiry": "2026-06-19",
            "contracts": "1",
            "premium": "1.05",
            "fees": "0.65",
        },
    )
    assert r.status_code == 201, r.text
    ex = new_account(c, name="Exchange", type="crypto-exchange", mask="2002")
    trade(c, ex["id"], "2025-03-01", "buy", "0.05", "80000", "BTC")
    trade(c, ex["id"], "2026-06-01", "sell", "0.05", "100000", "BTC")  # long, no basis: K
    trade(c, ex["id"], "2026-07-01", "buy", "0.02", "90000", "BTC")
    trade(c, ex["id"], "2026-08-03", "sell", "0.02", "95000", "BTC")  # acquired 2026: G
    w = new_account(c, name="Cold storage", type="crypto-wallet", mask="3003")
    trade(c, w["id"], "2026-02-02", "buy", "0.01", "85000", "BTC")
    trade(c, w["id"], "2026-05-04", "sell", "0.01", "98000", "BTC")  # self-custody: I
    me = c.get("/ui/api/session").json()["user"]["id"]
    r = c.post("/ui/api/tax-books", json={"year": 2026, "filers": [me]})
    assert r.status_code == 201, r.text
    return r.json()["id"]


@pytest.mark.parametrize(
    ("export", "golden"),
    [("8949.csv", "form-8949-2026.csv"), ("moneykata.txf", "moneykata-2026.txf")],
)
def test_the_exports_match_their_golden_files(alice, export, golden):
    book = portfolio(alice)
    r = alice.get(f"/ui/api/tax-books/{book}/exports/{export}")
    assert r.status_code == 200, r.text
    path = GOLDEN / golden
    if os.environ.get("MK_GOLDEN_WRITE") == "1":
        path.write_bytes(r.content)
    assert r.content == path.read_bytes()
