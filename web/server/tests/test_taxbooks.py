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
    # Bob confirms the marriage from his Profile (S10.10.4).
    assert bob.post(f"/ui/api/relationships/{r.json()['id']}/confirm").status_code == 200
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


# ---- Dependents (S8.14.5) ----


def person(c, name, sex="female", **kw):
    r = c.post("/ui/api/persons", json={"name": name, "sex": sex, **kw})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def child_of(c, parent, kid):
    r = c.post(
        "/ui/api/relationships",
        json={"person1Id": parent, "person2Id": kid, "relation": "child"},
    )
    assert r.status_code == 201, r.text


def dependent(c, book_id, person_id, **kw):
    return c.post(f"/ui/api/tax-books/{book_id}/dependents", json={"personId": person_id, **kw})


def test_dependents_are_suggested_from_the_family_tree_and_aged_on_dec_31(server, couple):
    alice, _, a_id, _ = couple
    pa = alice.get("/ui/api/profile").json()["personId"]
    carol = person(alice, "Carol Griffin", birthYear=2012, birthMonth=11, birthDay=30)
    emma = person(alice, "Emma Griffin", birthYear=2018)
    sam = person(alice, "Sam Griffin", "male", birthYear=2006)
    gran = person(alice, "Margaret Griffin", birthYear=1950)
    for kid in (carol, emma, sam):
        child_of(alice, pa, kid)
    b = book(alice, 2026, [a_id])
    cands = {
        x["name"]: x
        for x in alice.get(f"/ui/api/tax-books/{b['id']}/dependent-candidates").json()["items"]
    }
    assert "Alice" not in cands  # a filer isn't their own dependent
    assert cands["Carol Griffin"]["relation"] == "daughter"
    assert cands["Carol Griffin"]["age"] == 14
    assert cands["Carol Griffin"]["suggest"] == "qualifying child"
    # Sam is 20: a qualifying child only as a student.
    assert (cands["Sam Griffin"]["suggest"], cands["Sam Griffin"]["suggestIfStudent"]) == (
        "qualifying relative",
        "qualifying child",
    )
    assert cands["Margaret Griffin"]["suggest"] == "qualifying relative"

    r = dependent(alice, b["id"], carol, student=True)
    assert r.status_code == 201, r.text
    r = dependent(alice, b["id"], emma)
    d = {x["name"]: x for x in r.json()["dependents"]}
    assert d["Carol Griffin"]["age"] == 14 and d["Carol Griffin"]["under17"]
    assert not d["Carol Griffin"]["under13"]
    assert d["Emma Griffin"]["under13"] and d["Emma Griffin"]["agesOut"] == []
    assert dependent(alice, b["id"], gran, claimedAs="qualifying relative").status_code == 201
    assert dependent(alice, b["id"], carol).json()["code"] == "dependent-twice"
    assert dependent(alice, b["id"], pa).json()["code"] == "dependent-filer"
    assert dependent(alice, b["id"], emma, months=13).json()["code"] == "months-invalid"

    # Their documents: a student's 1098-T is expected.
    detail = alice.get(f"/ui/api/tax-books/{b['id']}").json()
    assert any(e["form"] == "1098-T" and "Carol" in e["why"] for e in detail["expected"])
    p = alice.get(f"/ui/api/tax-books/{b['id']}/panels").json()
    assert [x["name"] for x in p["dependents"]] == [
        "Carol Griffin",
        "Emma Griffin",
        "Margaret Griffin",
    ]
    assert p["students"] == [{"name": "Carol Griffin", "received1098T": False, "withdrawals529": 0}]

    # Changing and removing one.
    dep = next(x for x in detail["dependents"] if x["name"] == "Emma Griffin")
    r = alice.patch(
        f"/ui/api/tax-dependents/{dep['id']}",
        json={"personId": emma, "claimedAs": "qualifying child", "months": 6},
        headers={"If-Match": str(dep["version"])},
    )
    assert r.status_code == 200, r.text
    dep = next(x for x in r.json()["dependents"] if x["name"] == "Emma Griffin")
    assert dep["months"] == 6
    r = alice.delete(
        f"/ui/api/tax-dependents/{dep['id']}", headers={"If-Match": str(dep["version"])}
    )
    assert r.status_code == 200, r.text
    assert "Emma Griffin" not in {x["name"] for x in r.json()["parent"]["dependents"]}


def test_a_person_claimed_on_two_books_is_flagged_on_both(server, couple):
    alice, bob, a_id, b_id = couple
    kid = person(alice, "Carol Griffin", birthYear=2012)
    mine = book(alice, 2026, [a_id])
    theirs = book(bob, 2026, [b_id])
    assert dependent(alice, mine["id"], kid).status_code == 201
    r = dependent(bob, theirs["id"], kid)
    assert r.json()["dependents"][0]["claimedElsewhere"]
    d = alice.get(f"/ui/api/tax-books/{mine['id']}").json()
    assert d["dependents"][0]["claimedElsewhere"]
    issues = alice.get(f"/ui/api/tax-books/{mine['id']}/panels").json()["issues"]
    assert "Carol Griffin is claimed on another 2026 tax book too" in [i["text"] for i in issues]
    # A dependent's own book notes that they are claimed on another.
    pb = bob.get("/ui/api/profile").json()["personId"]
    assert dependent(alice, mine["id"], pb, claimedAs="qualifying relative").status_code == 201
    d = bob.get(f"/ui/api/tax-books/{theirs['id']}").json()
    assert d["claimedElsewhere"] == ["Bob"]


def test_a_dependent_childs_unearned_income_past_the_threshold_is_flagged(server, couple):
    alice, _, a_id, _ = couple
    kid = person(alice, "Carol Griffin", birthYear=2012)
    utma = new_account(alice, name="Carol's UTMA", type="brokerage")
    add(alice, utma["id"], "1900.00", day="2026-03-02", kind="dividend")
    add(alice, utma["id"], "1010.00", day="2026-06-02", kind="interest")
    b = book(alice, 2026, [a_id])
    r = dependent(alice, b["id"], kid, accountIds=["Acct_00000000000000000000000000"])
    assert r.json()["code"] == "account-not-counted"
    r = dependent(alice, b["id"], kid, accountIds=[utma["id"]])
    assert r.status_code == 201, r.text
    f = r.json()["form8615"]
    assert f == [
        {"name": "Carol Griffin", "unearned": 2910, "threshold": 2700, "accounts": ["Carol's UTMA"]}
    ]
    issues = alice.get(f"/ui/api/tax-books/{b['id']}/panels").json()["issues"]
    assert any(i["kind"] == "form-8615" for i in issues)


def test_next_years_book_copies_dependents_a_year_older(server, couple):
    alice, _, a_id, _ = couple
    carol = person(alice, "Carol Griffin", birthYear=2012)
    sam = person(alice, "Sam Griffin", "male", birthYear=2007)  # 19 in 2026
    ruth = person(alice, "Ruth Griffin", birthYear=2003)
    old = book(alice, 2025, [a_id])
    assert dependent(alice, old["id"], carol).status_code == 201
    assert dependent(alice, old["id"], sam).status_code == 201
    assert dependent(alice, old["id"], ruth, claimedAs="qualifying relative").status_code == 201
    new = book(alice, 2026, [a_id])
    assert new["dependentsLeftOut"] == ["Sam Griffin"]
    d = alice.get(f"/ui/api/tax-books/{new['id']}").json()
    ages = {x["name"]: x["age"] for x in d["dependents"]}
    assert ages == {"Carol Griffin": 14, "Ruth Griffin": 23}


def test_last_years_book_waits_for_every_filer_and_an_added_account_for_its_adder(server, couple):
    """S8.14.1, S8.14.2, S8.14.4 (P1): a book naming Bob shows nothing of his year before, and
    copies nothing from it, until he accepts; an account he added counts while he sees it."""
    alice, bob, a_id, b_id = couple
    kid = new_account(alice, name="Emma's custodial", type="brokerage")
    alice.put(f"/ui/api/shares/account/{kid['id']}", json={"users": {b_id: "read"}})
    last = book(bob, 2025, [b_id])
    r = bob.put(f"/ui/api/tax-books/{last['id']}/accounts/{kid['id']}", json={"counted": True})
    assert [a["name"] for a in r.json()["accounts"]] == ["Emma's custodial"]
    # Alice names Bob; until he accepts, the book has nothing of his 2025.
    joint = book(alice, 2026, [a_id, b_id], fromLastYear=True)
    from moneykata.store.entities.taxes import TaxBook, TaxBookAccount

    with server.db.read() as s:
        assert s.query(TaxBookAccount).filter_by(bookId=joint["id"]).count() == 0
        assert s.get(TaxBook, joint["id"]).fromLastYear
    assert bob.post(f"/ui/api/tax-books/{joint['id']}/accept").status_code == 200
    with server.db.read() as s:
        copied = s.query(TaxBookAccount).filter_by(bookId=joint["id"]).one()
        assert copied.accountId == kid["id"] and copied.addedById == b_id
        assert not s.get(TaxBook, joint["id"]).fromLastYear
    # Bob's added account counts in his own 2025 book only while he can see it.
    alice.put(f"/ui/api/shares/account/{kid['id']}", json={"users": {b_id: "none"}})
    d = bob.get(f"/ui/api/tax-books/{last['id']}").json()
    assert "Emma's custodial" not in [a["name"] for a in d["accounts"]]


def test_a_helper_edits_but_never_changes_what_the_book_counts(server, couple):
    """S8.14.3 (P7): write lets a helper edit filings, not add accounts; any filer shares it."""
    alice, bob, a_id, b_id = couple
    make_user(server, "gail")
    gail = sign_in(server, "gail")
    g_id = gail.get("/ui/api/session").json()["user"]["id"]
    acct = new_account(gail, name="Gail's", type="brokerage")
    b = book(alice, 2026, [a_id, b_id])
    bob.post(f"/ui/api/tax-books/{b['id']}/accept")
    # Bob, a filer who didn't make it, changes its sharing.
    r = bob.put(f"/ui/api/shares/tax-book/{b['id']}", json={"users": {g_id: "write"}})
    assert r.status_code == 200, r.text
    r = gail.put(f"/ui/api/tax-books/{b['id']}/accounts/{acct['id']}", json={"counted": True})
    assert r.status_code == 403 and r.json()["code"] == "filers-only"
    r = gail.post(f"/ui/api/tax-books/{b['id']}/filings", json={"form": "Form 1040"})
    assert r.status_code == 201, r.text
