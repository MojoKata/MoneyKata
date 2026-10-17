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


def option(c, acct, day, action, premium, **kw):
    r = c.post(
        f"/ui/api/accounts/{acct}/options",
        json={
            "date": day,
            "action": action,
            "underlying": kw.get("underlying", "MSFT"),
            "right": kw.get("right", "call"),
            "strike": kw.get("strike", "500"),
            "expiry": kw.get("expiry", "2027-01-15"),
            "contracts": "1",
            "premium": premium,
            "fees": "0.65",
        },
    )
    assert r.status_code == 201, r.text


def review_cases(c) -> str:
    """The figures the second review found wrong (section 4), each a case whose rows are
    worked out by hand in the comments."""
    # B1: average cost re-bases every lot at each sale: 300 paid, 300 of basis sold.
    avg = new_account(c, name="Average", type="brokerage", mask="4004", lotMethod="average")
    trade(c, avg["id"], "2026-01-05", "buy", "10", "10", "VXUS")
    trade(c, avg["id"], "2026-01-06", "buy", "10", "20", "VXUS")  # the average is 15
    trade(c, avg["id"], "2026-02-02", "sell", "5", "15", "VXUS")  # 75 against 75
    trade(c, avg["id"], "2026-03-02", "sell", "15", "15", "VXUS")  # 225 against 225
    # B2: a loss washed into a replacement that is itself sold at a loss and replaced again:
    # each loss deferred, the second including the first.
    chain = new_account(c, name="Chained", type="brokerage", mask="5005")
    trade(c, chain["id"], "2026-01-05", "buy", "10", "100", "NVDA")
    trade(c, chain["id"], "2026-02-02", "sell", "10", "80", "NVDA")  # 200 lost, washed
    trade(c, chain["id"], "2026-02-10", "buy", "10", "85", "NVDA")  # basis 850 + 200
    trade(c, chain["id"], "2026-03-02", "sell", "10", "70", "NVDA")  # 350 lost, washed
    trade(c, chain["id"], "2026-03-09", "buy", "10", "72", "NVDA")  # basis 720 + 350, held
    # B11: a written option is short term however long it was open (S3.3).
    written = new_account(c, name="Written", type="brokerage", mask="6006")
    trade(c, written["id"], "2025-01-02", "buy", "100", "1", "CASHX")  # cash for margin
    option(c, written["id"], "2025-01-10", "sell-to-open", "20.00")  # 2000 - 0.65
    option(c, written["id"], "2026-03-10", "buy-to-close", "12.00")  # 1200 + 0.65
    me = c.get("/ui/api/session").json()["user"]["id"]
    r = c.post("/ui/api/tax-books", json={"year": 2026, "filers": [me]})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_the_review_cases_match_their_golden_file(alice):
    # S17.5: a golden case for each figure the second review found wrong.
    book = review_cases(alice)
    r = alice.get(f"/ui/api/tax-books/{book}/exports/8949.csv")
    assert r.status_code == 200, r.text
    path = GOLDEN / "form-8949-review-2026.csv"
    if os.environ.get("MK_GOLDEN_WRITE") == "1":
        path.write_bytes(r.content)
    assert r.content == path.read_bytes()
    # B2: the second replacement, still held, carries both losses' second: 720 + 350.
    held = alice.get("/ui/api/positions").json()["open"]
    nvda = next(x for x in held if x["symbol"] == "NVDA")
    assert nvda["cost"] == "1070.00"
