"""Projections and assumptions (requirements S6.1–S6.9) and the tax tables (S16.11)."""

import datetime as dt
from decimal import Decimal

import pytest
from conftest import make_user, sign_in
from test_accounts import add, new_account

from moneykata import alerts, clock
from moneykata.projections import engine

T0 = dt.datetime(2026, 10, 13, 12, 0, tzinfo=dt.UTC)


@pytest.fixture
def frozen():
    clock.fix(T0)
    yield
    clock.fix(None)


@pytest.fixture
def alice(server, frozen):
    make_user(server, "alice")
    from moneykata.store.entities.users import User

    with server.db.tx() as s:
        u = s.query(User).filter_by(username="alice").one()
        u.birthYear = 1979
    return sign_in(server, "alice")


def retirement(c, **inputs):
    body = {
        "name": "Retire at 62",
        "goal": "retirement",
        "builtOn": {"kind": "typed", "amount": 500000, "allocation": {"usStocks": 60, "bonds": 40}},
        "inputs": {
            "people": [{"name": "Alice", "birthYear": 1979, "retireAge": 62}],
            "contribution": {"amount": 30000, "growth": 3},
            "withdrawal": {"method": "fourPercent"},
            "income": [{"label": "Social Security", "person": 0, "fromAge": 67, "monthly": 2900}],
            **inputs,
        },
    }
    r = c.post("/ui/api/projections", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_the_same_inputs_give_the_same_figures(alice):
    p = retirement(alice)
    again = alice.get(f"/ui/api/projections/{p['id']}").json()
    assert again["result"]["percentiles"]["50"] == p["result"]["percentiles"]["50"]
    res = p["result"]
    assert res["years"][0] == 2026 and res["years"][-1] == 1979 + 95
    lo, mid, hi = (res["percentiles"][k][-10] for k in ("10", "50", "90"))
    assert lo <= mid <= hi
    assert 0 <= res["answer"]["chance"] <= 1 and res["answer"]["retireYear"] == 2041
    assert p["headline"].endswith("chance the money lasts to 95")


def test_retiring_later_makes_the_money_more_likely_to_last(alice):
    tight = {"withdrawal": {"method": "fixed", "amount": 90000}, "income": []}
    early = retirement(alice, people=[{"name": "A", "birthYear": 1979, "retireAge": 55}], **tight)
    late = retirement(alice, people=[{"name": "A", "birthYear": 1979, "retireAge": 67}], **tight)
    assert late["result"]["answer"]["chance"] > early["result"]["answer"]["chance"] + Decimal("0.2")


def test_a_savings_target_says_how_likely_and_what_would_do_it(alice):
    r = alice.post(
        "/ui/api/projections",
        json={
            "name": "House deposit",
            "goal": "savings",
            "builtOn": {"kind": "typed", "amount": 38200, "allocation": {"cash": 100}},
            "inputs": {"target": 60000, "date": "2028-10-01", "monthly": 300},
        },
    )
    assert r.status_code == 201, r.text
    a = r.json()["result"]["answer"]
    assert a["chance"] < 0.5, "300 a month falls short"
    assert 800 < a["neededMonthly"] < 1000


def test_inputs_are_checked(alice):
    r = alice.post(
        "/ui/api/projections",
        json={
            "name": "",
            "goal": "lottery",
            "builtOn": {"kind": "accounts", "ids": ["Acct_nope"]},
            "inputs": {"fees": 9, "date": "2001-01-01"},
        },
    )
    assert r.status_code == 422
    assert {e["field"] for e in r.json()["errors"]} >= {
        "name",
        "goal",
        "builtOn",
        "inputs.fees",
        "inputs.date",
    }


def test_built_on_accounts_starts_from_their_value(alice):
    acct = new_account(alice, name="Savings", type="savings")
    add(alice, acct["id"], "12000.00", "2026-10-01")
    r = alice.post(
        "/ui/api/projections",
        json={
            "name": "Car",
            "goal": "savings",
            "builtOn": {"kind": "accounts", "ids": [acct["id"]]},
            "inputs": {"target": 20000, "date": "2028-01-01", "monthly": 250},
        },
    )
    res = r.json()["result"]
    assert res["start"] == 12000.0 and res["weights"] == {"cash": 1.0}
    assert r.json()["builtOnLabel"] == "Savings"


def test_one_active_plan_per_subject_and_its_baseline(alice):
    a = retirement(alice)
    b = retirement(alice, contribution={"amount": 40000, "growth": 3})
    assert alice.post(f"/ui/api/projections/{a['id']}/activate").json() == {"replaced": None}
    assert alice.post(f"/ui/api/projections/{b['id']}/activate").json() == {
        "replaced": "Retire at 62"
    }
    rows = {p["id"]: p for p in alice.get("/ui/api/projections").json()}
    assert rows[b["id"]]["active"] and not rows[a["id"]]["active"]
    got = alice.get(f"/ui/api/projections/{b['id']}").json()
    assert got["tracking"]["status"] == "untracked", "a typed amount has nothing to track"
    # Changing inputs keeps the baseline unless asked to re-baseline.
    base = got["result"]["percentiles"]["50"]
    r = alice.patch(
        f"/ui/api/projections/{b['id']}",
        json={"inputs": {**got["inputs"], "fees": 1.0}},
        headers={"If-Match": f'"{got["version"]}"'},
    )
    assert r.status_code == 200 and r.json()["result"]["percentiles"]["50"] != base


def test_tracking_against_the_band_and_the_alert_when_behind(server, alice):
    acct = new_account(alice, name="Brokerage cash", type="savings")
    add(alice, acct["id"], "100000.00", "2026-10-01")
    r = alice.post(
        "/ui/api/projections",
        json={
            "name": "Nest egg",
            "goal": "savings",
            "builtOn": {"kind": "accounts", "ids": [acct["id"]]},
            "inputs": {"target": 150000, "date": "2030-01-01", "monthly": 500},
        },
    )
    pid = r.json()["id"]
    alice.post(f"/ui/api/projections/{pid}/activate")
    assert alice.get(f"/ui/api/projections/{pid}").json()["tracking"]["status"] == "on track"
    # Most of it is spent, and a month passes.
    add(alice, acct["id"], "-60000.00", "2026-10-20")
    clock.fix(dt.datetime(2026, 11, 3, 12, tzinfo=dt.UTC))
    alice2 = sign_in(server, "alice")
    assert alice2.get(f"/ui/api/projections/{pid}").json()["tracking"]["status"] == "behind"
    opened = alerts.evaluate(server)
    assert [a.kind for a in opened] == ["projection-behind"]
    plans = alice2.get("/ui/api/dashboard/plans").json()
    assert plans[0]["status"] == "behind" and plans[0]["actual"]


def test_assumptions_are_each_users_and_checked(alice):
    got = alice.get("/ui/api/assumptions").json()
    figures = got["figures"]
    assert figures["inflation"] == 2.5 and figures["classes"]["usStocks"]["return"] == 7.0
    figures["classes"]["usStocks"]["return"] = 6.0
    assert alice.put("/ui/api/assumptions", json=figures).status_code == 200
    assert (
        alice.get("/ui/api/assumptions").json()["figures"]["classes"]["usStocks"]["return"] == 6.0
    )
    figures["inflation"] = 40
    r = alice.put("/ui/api/assumptions", json=figures)
    assert r.status_code == 422 and r.json()["errors"][0]["field"] == "inflation"


def test_bitcoin_models_compare(alice):
    rows = {r["model"]: r for r in alice.get("/ui/api/bitcoin-models").json()["rows"]}
    assert set(rows) == {"powerLaw", "logRegression", "stockToFlow", "saylor", "ark"}
    assert rows["ark"]["at"]["2030"] == pytest.approx(1_200_000, rel=0.01)
    assert rows["saylor"]["at"]["2045"] == pytest.approx(13_000_000, rel=0.01)
    assert "stake" in rows["saylor"]["record"] or "holds" in rows["saylor"]["record"]


def test_tax_tables_ship_and_can_be_corrected(server, frozen, admin_client):
    t = admin_client.get("/ui/api/settings/tax-tables").json()
    assert t["year"] == 2026
    ira = next(r for r in t["rows"] if r["key"] == "iraLimit")
    assert ira["value"] == 7500 and not ira["corrected"]
    r = admin_client.put(
        "/ui/api/settings/tax-tables", json={"year": 2026, "values": {"iraLimit": 8000}}
    )
    assert next(x for x in r.json()["rows"] if x["key"] == "iraLimit")["corrected"]
    r = admin_client.put(
        "/ui/api/settings/tax-tables", json={"year": 2026, "values": {"btcArk2030": [1, 2]}}
    )
    assert r.status_code == 422
    # The shipped value again removes the correction.
    r = admin_client.put(
        "/ui/api/settings/tax-tables", json={"year": 2026, "values": {"iraLimit": 7500}}
    )
    assert not next(x for x in r.json()["rows"] if x["key"] == "iraLimit")["corrected"]


def test_a_bitcoin_model_with_cases_gives_three_paths(server, alice):
    from moneykata import ids
    from moneykata.store.entities.accounts import Instrument

    with server.db.tx() as s:
        s.add(
            Instrument(
                id=ids.new_id("Instr"), symbol="BTC", name="Bitcoin", instrumentClass="crypto"
            )
        )
    p = retirement(
        alice,
        bitcoinModel="ark",
    )
    # A typed amount with some crypto in it.
    r = alice.patch(
        f"/ui/api/projections/{p['id']}",
        json={
            "builtOn": {
                "kind": "typed",
                "amount": 100000,
                "allocation": {"usStocks": 80, "crypto": 20},
            }
        },
        headers={"If-Match": f'"{p["version"]}"'},
    )
    sc = r.json()["result"]["scenarios"]
    assert set(sc) == {"bear", "base", "bull"}
    assert sc["bear"][-1] < sc["base"][-1] < sc["bull"][-1]


def test_engine_withdrawals_run_the_money_out():
    plan = engine.Plan(
        start=100000,
        weights={"cash": 1.0},
        returns={"cash": 0.0},
        vols={"cash": 0.0},
        inflation=0.0,
        fees=0.0,
        first_year=2026,
        years=12,
        withdraw_from=1,
        withdrawal={"method": "fixed", "amount": 20000},
    )
    r = engine.run(plan)
    assert r.lasted == 0.0 and r.percentiles[50][5] == 0.0 and r.percentiles[50][4] == 20000
