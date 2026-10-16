import asyncio
import datetime as dt
import threading
import time
from decimal import Decimal

import httpx
import pytest
from pydantic import ValidationError

from moneykata import exactjson, net
from moneykata.events import Broker
from moneykata.jobs import Jobs
from moneykata.ratelimit import SignInGuard, Window
from moneykata.tasks import Daily, Every, ProviderLimits, TaskError, Tasks
from moneykata.ui.conventions import Model, Money, Paging
from moneykata.ui.stream import stream

UTC = dt.UTC


def test_daily_runs_at_its_time_in_its_zone():
    d = Daily(lambda: (dt.time(18, 0), "America/New_York"))
    last = dt.datetime(2026, 10, 12, 22, 0, tzinfo=UTC)  # 18:00 EDT
    assert d.next_due(last, last) == dt.datetime(2026, 10, 13, 22, 0, tzinfo=UTC)
    started = dt.datetime(2026, 10, 12, 12, 0, tzinfo=UTC)
    # Never run: yesterday's run is owed, so it is due at once.
    assert d.next_due(None, started) <= started


def test_every_waits_before_its_first_run():
    e = Every(3600, first_after=30)
    t = dt.datetime(2026, 1, 1, tzinfo=UTC)
    assert e.next_due(None, t) == t + dt.timedelta(seconds=30)
    assert e.next_due(t, t) == t + dt.timedelta(hours=1)


def test_provider_limits_spread_calls():
    clock = [0.0]
    limits = ProviderLimits(clock=lambda: clock[0])
    limits.set("tiingo", [(2, 60), (3, 3600)])
    assert limits.delay("tiingo") == 0
    assert limits.delay("tiingo") == 0
    assert limits.delay("tiingo") == pytest.approx(60)
    clock[0] = 61
    assert limits.delay("tiingo") == 0
    clock[0] = 130
    assert limits.delay("tiingo") == pytest.approx(3600 - 130)


def test_tasks_record_runs_and_keep_error_text_out_unless_safe():
    recorded = {}
    done = threading.Event()

    def record(name, run):
        recorded[name] = run
        if len(recorded) == 2:
            done.set()

    tasks = Tasks(record=record)

    def leaky(ctx):
        raise ValueError("Checking 1234 is short $50")

    def safe(ctx):
        raise TaskError("Tiingo answered 401")

    tasks.register("leaky", leaky, None)
    tasks.register("safe", safe, None)
    tasks.run_now("leaky")
    tasks.run_now("safe")
    tasks.tick()
    assert done.wait(5)
    tasks.stop()
    assert recorded["leaky"].error == "ValueError"
    assert recorded["safe"].error == "TaskError: Tiingo answered 401"


def test_egress_guard():
    guard = net.Guard(
        resolver=lambda h, p: {
            "api.tiingo.com": ["203.0.113.5"],
            "evil.example": ["169.254.169.254"],
            "node.lan": ["127.0.0.1"],
        }[h]
    )
    guard.allow(["api.tiingo.com", "evil.example", "node.lan"])
    guard.check("api.tiingo.com", 443)
    with pytest.raises(net.EgressRefused, match="not a host"):
        guard.check("example.com", 443)
    with pytest.raises(net.EgressRefused, match="metadata"):
        guard.check("evil.example", 443)
    with pytest.raises(net.EgressRefused, match="loopback"):
        guard.check("node.lan", 50001)
    guard.allow(["node.lan"], allowed_by_name=["node.lan"])
    guard.check("node.lan", 50001)
    with pytest.raises(net.EgressRefused):
        guard.check("127.0.0.1", 80)


def test_client_refuses_before_connecting():
    client = net.Client(net.Guard())
    with pytest.raises(httpx.TransportError):
        client.get("https://example.com/")


def test_windows_and_sign_in_lockout():
    clock = [0.0]
    w = Window(3, 60, clock=lambda: clock[0])
    assert [w.hit("s") for _ in range(4)][-1] == pytest.approx(60)
    clock[0] = 60
    assert w.hit("s") == 0

    g = SignInGuard(clock=lambda: clock[0])
    for _ in range(9):
        assert not g.failed("alice", "10.0.0.5")
    assert g.failed("Alice", "10.0.0.5")
    # The address is locked; the username is only slowed, from any address (S13.7.5.1).
    assert g.locked("10.0.0.5") == pytest.approx(15 * 60)
    assert g.locked("10.0.0.6") == 0
    assert g.delay("alice", "10.0.0.6") == 4.0  # ten failures: half a second past the third
    g.succeeded("alice")
    assert g.delay("alice", "10.0.0.6") == 0
    clock[0] += 15 * 60
    assert g.locked("10.0.0.5") == 0


def test_money_fields_refuse_floats():
    class Body(Model):
        amount: Money

    # In JSON an amount is an exact number literal (S13.8.2); in Python, a Decimal.
    assert exactjson.dumps(Body(amount="12.30").model_dump(mode="json")) == '{"amount": 12.30}'
    assert Body(amount=Decimal("12.3")).model_dump() == {"amount": Decimal("12.3")}
    with pytest.raises(ValidationError):
        Body(amount=12.3)  # never through a float
    with pytest.raises(ValidationError):
        Body(amount="12.345")
    with pytest.raises(ValidationError):
        Body(amount="1", extra=1)


def test_paging_takes_an_offset_and_counts_the_whole():
    p = Paging(offset=2, limit=2)
    assert p.page([1, 2, 3, 4, 5]) == {"items": [3, 4], "total": 5, "offset": 2, "limit": 2}
    assert Paging(offset=10, limit=2).page([1, 2]) == {
        "items": [],
        "total": 2,
        "offset": 10,
        "limit": 2,
    }


def test_stream_delivers_from_threads_and_ends_on_close():
    async def scenario():
        broker = Broker()
        broker.bind(asyncio.get_running_loop())
        sub = broker.subscribe("User_a", "h1")
        other = broker.subscribe("User_b", "h2")

        async def ok():
            return None

        out = []

        async def read():
            async for chunk in stream(broker, sub, {"version": "1"}, ok, seconds=5):
                out.append(chunk.decode())

        reader = asyncio.create_task(read())
        await asyncio.sleep(0)
        threading.Thread(target=broker.publish, args=("prices", {"asOf": "x"}, ["User_a"])).start()
        await asyncio.sleep(0.1)
        await broker.close_all()
        await asyncio.wait_for(reader, 2)
        assert other.queue.qsize() == 1  # only the closing notice: prices went to User_a
        return out

    out = asyncio.run(scenario())
    assert out[0].startswith("retry:")
    assert out[1].startswith("event: hello")
    assert out[2] == 'event: prices\ndata: {"asOf": "x"}\n\n'
    assert len(out) == 3


def test_stream_ends_when_the_session_does():
    async def scenario():
        broker = Broker()
        broker.bind(asyncio.get_running_loop())
        sub = broker.subscribe("User_a", "h1")

        async def ended():
            return "signed-out"

        return [c.decode() async for c in stream(broker, sub, {}, ended, seconds=5, keepalive=0.05)]

    out = asyncio.run(scenario())
    assert out[-1] == 'event: session\ndata: {"state": "signed-out"}\n\n'


def test_jobs_are_their_users_own():
    seen = []
    jobs = Jobs(announce=seen.append)
    job = jobs.create("import", "User_a")
    assert jobs.get(job.id, "User_b") is None
    assert jobs.get(job.id, "User_a") is job
    jobs.update(job, state="done", progress=1.0, result={"added": 3})
    assert seen == [job] and job.finished is not None
    time.sleep(0)


def test_run_now_starts_at_once_once_the_tasks_have_started():
    ran = threading.Event()
    tasks = Tasks()
    tasks.register("backups", lambda ctx: ran.set(), None)

    async def main():
        tasks.start()  # its first tick runs nothing: the task has no schedule
        await asyncio.sleep(0)
        try:
            assert tasks.run_now("backups")
            return await asyncio.to_thread(ran.wait, 2)  # well inside a 15-second tick
        finally:
            tasks.stop()

    assert asyncio.run(main())
