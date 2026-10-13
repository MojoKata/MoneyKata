import datetime as dt
import json
from decimal import Decimal as D

import pytest
from conftest import make_user, sign_in
from sqlalchemy import func, select

from moneykata import clock, figures, ids, valuation
from moneykata.ledger.types import investing
from moneykata.prices import SOURCES, SourceError, TickerSource, register
from moneykata.prices import refresh as pricing
from moneykata.prices.base import Ref
from moneykata.prices.coinbase import Coinbase
from moneykata.prices.stub import Stub, walk
from moneykata.prices.tiingo import Tiingo
from moneykata.store.entities.accounts import Account
from moneykata.store.entities.prices import Price, PriceSource
from moneykata.store.repos import ledger as repo

TODAY = dt.date.today()


class FakeResponse:
    def __init__(self, status):
        self.status_code = status


class FakeClient:
    def __init__(self, answers):
        self.answers = answers
        self.calls = []

    def get_bytes(self, url, **kw):
        self.calls.append((url, kw))
        status, body = self.answers(url)
        return FakeResponse(status), json.dumps(body).encode()


def test_stub_is_repeatable_and_waits_for_the_close():
    assert walk("VTI", dt.date(2026, 3, 2)) == walk("VTI", dt.date(2026, 3, 2))
    rows = Stub(None, None).history(Ref("i", "VTI", "etf"), TODAY - dt.timedelta(days=10), TODAY)
    assert rows and rows[-1][0] < TODAY
    assert all(d.weekday() < 5 for d, _ in rows)
    crypto = Stub(None, None).history(
        Ref("i", "BTC", "crypto"), TODAY - dt.timedelta(days=3), TODAY
    )
    assert crypto[-1][0] == TODAY


def test_tiingo_reads_closes_and_sends_its_key_in_a_header():
    client = FakeClient(
        lambda url: (
            200,
            [
                {"date": "2026-10-08T00:00:00.000Z", "close": 250.5},
                {"date": "2026-10-09T00:00:00.000Z", "close": 251.25},
            ],
        )
    )
    rows = Tiingo(client, "secret-key").history(
        Ref("i", "VTI", "etf"), dt.date(2026, 10, 8), dt.date(2026, 10, 9)
    )
    assert rows == [(dt.date(2026, 10, 8), D("250.5")), (dt.date(2026, 10, 9), D("251.25"))]
    url, kw = client.calls[0]
    assert "secret-key" not in url and kw["headers"]["Authorization"] == "Token secret-key"
    with pytest.raises(SourceError, match="refused the key"):
        Tiingo(FakeClient(lambda u: (401, {})), "bad").history(Ref("i", "VTI", "etf"), TODAY, TODAY)
    with pytest.raises(SourceError, match="needs its API key"):
        Tiingo(client, None).history(Ref("i", "VTI", "etf"), TODAY, TODAY)


def test_coinbase_pages_daily_candles():
    def answers(url):
        return 200, [
            [int(dt.datetime(2026, 1, 2, tzinfo=dt.UTC).timestamp()), 1, 2, 1, 98000.5, 10]
        ]

    client = FakeClient(answers)
    rows = Coinbase(client, None).history(
        Ref("i", "BTC", "crypto"), dt.date(2025, 1, 1), dt.date(2026, 1, 31)
    )
    assert rows == [(dt.date(2026, 1, 2), D("98000.5"))]
    assert len(client.calls) == 2  # 300 days a call


def test_coinbase_leaves_out_todays_open_candle():
    def stamp(day):
        return int(dt.datetime.combine(day, dt.time(), dt.UTC).timestamp())

    yesterday = TODAY - dt.timedelta(days=1)
    client = FakeClient(
        lambda url: (200, [[stamp(TODAY), 1, 2, 1, 101.0, 1], [stamp(yesterday), 1, 2, 1, 99.5, 1]])
    )
    clock.fix(dt.datetime.combine(TODAY, dt.time(21), dt.UTC))
    try:
        rows = Coinbase(client, None).history(Ref("i", "BTC", "crypto"), yesterday, TODAY)
    finally:
        clock.fix(None)
    assert rows == [(yesterday, D("99.5"))]
    assert f"end={yesterday.isoformat()}T23:59:59Z" in client.calls[0][0]


@register
class Broken(TickerSource):
    name = "broken-test"
    label = "Broken"
    classes = frozenset({"etf"})

    def history(self, ref, start, end):
        raise SourceError("Broken answered HTTP 500")


def _book(server, user):
    with server.db.tx() as s:
        a = Account(id=ids.new_id("Acct"), ownerId=user.id, name="B", type="brokerage")
        s.add(a)
        s.flush()
        inst = repo.instrument(s, "VTI", "Total market", "etf")
        from moneykata.store.entities.accounts import Lot, Transaction

        t = Transaction(
            id=ids.new_id("Txn"),
            accountId=a.id,
            date=TODAY - dt.timedelta(days=20),
            kind="buy",
            amount=D("-1000.00"),
            instrumentId=inst.id,
            quantity=D(4),
            price=D(250),
        )
        s.add(t)
        s.flush()
        s.add(
            Lot(
                id=ids.new_id("Lot"),
                accountId=a.id,
                instrumentId=inst.id,
                transactionId=t.id,
                acquiredOn=t.date,
                quantity=D(4),
                costBasis=D(1000),
            )
        )
        return a.id, inst.id


def _source(server, name, pref):
    with server.db.tx() as s:
        s.add(
            PriceSource(
                id=ids.new_id("Src"), name=name, enabled=True, preference=json.dumps({"etf": pref})
            )
        )


def test_refresh_falls_back_records_errors_and_stores_once(server):
    pricing.install()
    server.config = server.config.__class__(**{**server.config.__dict__, "dev": True})
    user = make_user(server, "alice")
    account_id, inst_id = _book(server, user)
    _source(server, "broken-test", 1)
    _source(server, "stub", 2)
    result = pricing.refresh(server)
    assert result["stored"] > 10
    with server.db.read() as s:
        rows = {r.name: r for r in s.scalars(select(PriceSource))}
        assert rows["broken-test"].lastError == "Broken answered HTTP 500"
        assert rows["stub"].lastOkAt is not None and rows["stub"].lastError is None
        n = s.scalar(select(func.count()).select_from(Price))
        p = pricing.stored_closes(s, [inst_id], TODAY)[inst_id]
        assert p.source == "close" and not p.stale
    assert pricing.refresh(server)["stored"] == 0  # nothing new: nothing stored twice
    with server.db.read() as s:
        assert s.scalar(select(func.count()).select_from(Price)) == n
        a = s.get(Account, account_id)
        led = repo.load(s, a)
        value = valuation.account_value(s, led, investing(a.type))
        ser = valuation.series(s, led, True, TODAY - dt.timedelta(days=60), TODAY, 3)
        assert ser[-1] == (TODAY, value)  # the chart ends where the balance is


def test_refresh_fails_when_every_source_does(server):
    user = make_user(server, "alice")
    _book(server, user)
    _source(server, "broken-test", 1)
    with pytest.raises(SourceError):
        pricing.refresh(server)


def test_staleness():
    friday = dt.date(2026, 10, 9)
    assert not pricing.is_stale("etf", "close", friday, dt.date(2026, 10, 13))
    assert pricing.is_stale("etf", "close", friday, dt.date(2026, 10, 15))
    assert pricing.is_stale("crypto", "close", friday, dt.date(2026, 10, 12))
    assert not pricing.is_stale("other", "manual", friday, dt.date(2026, 12, 31))
    assert pricing.is_stale("other", "manual", friday, dt.date(2027, 2, 1))


def test_price_sources_in_settings(admin_client, server):
    view = admin_client.get("/ui/api/price-sources").json()
    names = {s["name"] for s in view["available"]}
    assert {"tiingo", "coinbase", "manual"} <= names and "stub" not in names
    assert view["refreshTime"] == "18:00"
    r = admin_client.post("/ui/api/price-sources", json={"name": "tiingo"})
    assert r.status_code == 201
    src = r.json()["sources"][0]
    assert src["enabled"] is False and src["needsKey"] and src["key"] is None
    r = admin_client.patch(
        f"/ui/api/price-sources/{src['id']}",
        json={"enabled": True},
        headers={"If-Match": str(src["version"])},
    )
    assert r.json()["code"] == "key-needed"
    r = admin_client.patch(
        f"/ui/api/price-sources/{src['id']}",
        json={"apiKey": "abcdef0123456789", "enabled": True},
        headers={"If-Match": str(src["version"])},
    )
    assert r.status_code == 200, r.text
    row = r.json()["sources"][0]
    assert row["enabled"] and row["key"]["setBy"] == "Ada Admin"
    assert "abcdef0123456789" not in r.text
    with pytest.raises(Exception, match="not a host"):
        server.guard.check("api.exchange.coinbase.com", 443)
    assert admin_client.post("/ui/api/price-sources", json={"name": "tiingo"}).status_code == 409
    assert admin_client.post("/ui/api/price-sources", json={"name": "stub"}).status_code == 422
    r = admin_client.delete(
        f"/ui/api/price-sources/{src['id']}", headers={"If-Match": str(row["version"])}
    )
    assert r.status_code == 204
    from moneykata.store.repos import secrets as secret_repo

    with server.db.read() as s:
        assert secret_repo.info(s, "PriceSource", src["id"], "apiKey") is None


def test_typed_prices_win_and_only_for_holders(server):
    pricing.install()
    user = make_user(server, "alice")
    make_user(server, "bob")
    _account_id, inst_id = _book(server, user)
    alice, bob = sign_in(server, "alice"), sign_in(server, "bob")
    day = (TODAY - dt.timedelta(days=1)).isoformat()
    assert (
        bob.post(
            f"/ui/api/instruments/{inst_id}/prices", json={"date": day, "price": "300"}
        ).status_code
        == 404
    )
    r = alice.post(f"/ui/api/instruments/{inst_id}/prices", json={"date": day, "price": "300"})
    assert r.status_code == 201
    closes = alice.get(f"/ui/api/instruments/{inst_id}/prices").json()
    assert closes[-1] == {"date": day, "close": "300", "source": "manual"}
    status = alice.get("/ui/api/prices/status").json()
    assert status["stale"] is False and status["running"] is False
    assert alice.post("/ui/api/prices/refresh").status_code in (202, 503)


def test_sources_registered():
    assert {"tiingo", "coinbase", "manual", "stub"} <= set(SOURCES)


def test_a_server_that_holds_nothing_has_no_stale_prices(admin_client, server):
    with server.db.tx() as s:
        figures.ensure_benchmarks(s)  # as a real start does
    with server.db.read() as s:
        assert pricing.priced(s), "the benchmarks are watched from the start"
    assert admin_client.get("/ui/api/prices/status").json()["stale"] is False
    attention = admin_client.get("/ui/api/dashboard").json()["attention"]
    assert all(a["kind"] != "stale-prices" for a in attention)
