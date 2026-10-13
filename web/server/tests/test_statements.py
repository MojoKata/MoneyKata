"""Statement import (requirements S1.3.3): the parser on the layouts most statements share."""

import datetime as dt
from decimal import Decimal

from moneykata.importers import statements

TODAY = dt.date(2026, 10, 13)

UMB = """UMB Bank, n.a.
Free Checking
Statement Period: 09/01/26 - 09/30/26
Account Summary
Beginning Balance on 09/01/26 $5,710.50
Deposits and Other Credits 4,820.00
Withdrawals and Other Debits 4,410.00
Ending Balance on 09/30/26 $6,120.50
Deposits and Other Credits
09/15 ACME CORP PAYROLL 2,410.00
09/30 ACME CORP PAYROLL 2,410.00
Withdrawals and Other Debits
09/03 POS KROGER #412 142.18
09/10 ONLINE TRANSFER TO SAVINGS 1,000.00
09/22 DUKE ENERGY 188.40
Checks Paid
09/12 1043 3,079.42
Daily Balance
09/03 5,568.32
09/10 4,568.32
"""

SCHWAB = """Charles Schwab Bank
Schwab Bank Investor Checking
Statement Period: September 1-30, 2026
Beginning Balance $1,000.00
Ending Balance $1,207.82
Transaction Detail
Date Description Withdrawals Deposits Balance
09/03 Visa Purchase BLUE BOTTLE 42.18 957.82
09/15 Funds Transfer from Brokerage 500.00 1,457.82
09/20 ATM Fee Rebate 3.00 1,460.82
09/28 Bill Pay CITY POWER 253.00 1,207.82
"""

CARD = """Example Card Co
Opening/Closing Date 08/29/26 - 09/28/26
Previous Balance $1,203.11
Payments and Credits -$1,203.11
Purchases +$842.50
New Balance $842.50
Transactions
08/31 KROGER #412 142.18
09/05 PAYMENT THANK YOU -1,203.11
09/12 DELTA AIR 700.32
"""


def parse(text, **kw):
    return statements.parse(text.splitlines(), TODAY, **kw)


def test_a_umb_checking_statement_by_its_sections():
    st = parse(UMB)
    assert (st.periodStart, st.periodEnd) == (dt.date(2026, 9, 1), dt.date(2026, 9, 30))
    assert (st.opening, st.closing) == (Decimal("5710.50"), Decimal("6120.50"))
    assert [(r.date.day, r.amount) for r in st.rows] == [
        (15, Decimal("2410.00")),
        (30, Decimal("2410.00")),
        (3, Decimal("-142.18")),
        (10, Decimal("-1000.00")),
        (22, Decimal("-188.40")),
        (12, Decimal("-3079.42")),
    ]
    assert st.difference == 0, "the daily balances are not transactions"
    assert st.institution.startswith("UMB Bank")


def test_a_schwab_statement_by_its_running_balance():
    st = parse(SCHWAB)
    assert (st.periodStart, st.periodEnd) == (dt.date(2026, 9, 1), dt.date(2026, 9, 30))
    assert [r.amount for r in st.rows] == [
        Decimal("-42.18"),
        Decimal("500.00"),
        Decimal("3.00"),
        Decimal("-253.00"),
    ]
    assert all(r.confidence >= 97 for r in st.rows) and st.difference == 0


def test_a_card_statement_is_turned_to_the_accounts_side():
    st = parse(CARD, card=True)
    assert (st.opening, st.closing) == (Decimal("-1203.11"), Decimal("-842.50"))
    assert [r.amount for r in st.rows] == [
        Decimal("-142.18"),
        Decimal("1203.11"),
        Decimal("-700.32"),
    ]
    assert st.rows[0].date == dt.date(2026, 8, 31) and st.difference == 0


def test_a_statement_that_does_not_add_up_says_by_how_much():
    st = parse(UMB.replace("09/22 DUKE ENERGY 188.40\n", ""))
    assert st.difference == Decimal("-188.40")


def test_the_layout_learned_is_applied_next_time():
    text = """Prairie Credit Union
Statement Period 10/01/26 - 10/31/26
Beginning Balance 100.00
Ending Balance 70.00
Money Movement
10/02 COFFEE 10.00
10/05 RENT 20.00
Fee Detail
10/05 SERVICE CHARGE WAIVED 5.00
"""
    first = parse(text)
    assert first.difference != 0
    # The person makes the first section money out and takes the waived fee out.
    kept = [
        statements.StatementRow(r.date, r.description, -abs(r.amount), section=r.section)
        for r in first.rows
        if not r.description.startswith("SERVICE")
    ]
    layout = statements.learn(None, first, kept)
    again = parse(text, layout=layout)
    assert [r.amount for r in again.rows] == [Decimal("-10.00"), Decimal("-20.00")]
    assert again.difference == 0


# ---------- through the server ----------


def _import(c, account_id, data, name="statement.pdf"):
    from test_accounts import wait_job

    r = c.post(
        f"/ui/api/accounts/{account_id}/imports",
        files={"file": (name, data, "application/pdf")},
    )
    assert r.status_code == 202, r.text
    return wait_job(c, r.json())


def test_a_statement_is_checked_then_saved_once(server):
    from conftest import make_user, sign_in
    from test_accounts import new_account
    from test_reading import text_pdf

    make_user(server, "alice")
    c = sign_in(server, "alice")
    acct = new_account(c, institution="UMB Bank")
    pdf = text_pdf(UMB.splitlines())
    job = _import(c, acct["id"], pdf)
    assert job["state"] == "done", job
    review = job["result"]
    assert review["needsReview"] and review["method"] == "text"
    assert len(review["rows"]) == 6 and review["opening"] == "5710.50"
    rows = [
        {"date": x["date"], "description": x["description"], "amount": x["amount"]}
        for x in review["rows"]
    ]
    body = {
        "periodStart": review["periodStart"],
        "periodEnd": review["periodEnd"],
        "opening": review["opening"],
        "closing": review["closing"],
        "rows": rows[:-1],
    }
    r = c.post(f"/ui/api/imports/{review['uploadId']}/statement", json=body)
    assert r.status_code == 422 and r.json()["errors"][0]["field"] == "acceptDifference"
    body["rows"] = rows
    r = c.post(f"/ui/api/imports/{review['uploadId']}/statement", json=body)
    assert r.status_code == 200, r.text
    done = r.json()["result"]
    assert done["added"] == 6
    # The statement is kept as a receipt on the account, its text searchable.
    rc = c.get(f"/ui/api/receipts/{done['receiptId']}").json()
    assert rc["links"][0]["accountId"] == acct["id"] and "PAYROLL" in rc["text"]
    # The balances are the account's anchors: the Reconcile tab checks them.
    rec = c.get(f"/ui/api/accounts/{acct['id']}/reconcile").json()
    assert [k["source"] for k in rec["checks"]].count("statement") == 2
    # The same statement again adds nothing.
    again = _import(c, acct["id"], pdf)["result"]
    assert all(x["present"] for x in again["rows"])
    r = c.post(
        f"/ui/api/imports/{again['uploadId']}/statement",
        json={**body, "rows": rows},
    )
    assert r.json()["result"]["added"] == 0


def test_statement_reading_can_be_off(server, admin_client):
    from conftest import make_user, sign_in
    from test_accounts import new_account
    from test_reading import text_pdf

    assert admin_client.patch("/ui/api/settings", json={"readStatements": False}).status_code == 200
    make_user(server, "alice")
    c = sign_in(server, "alice")
    acct = new_account(c)
    r = c.post(
        f"/ui/api/accounts/{acct['id']}/imports",
        files={"file": ("s.pdf", text_pdf(UMB.splitlines()), "application/pdf")},
    )
    assert r.status_code == 415 and r.json()["code"] == "statements-off"
