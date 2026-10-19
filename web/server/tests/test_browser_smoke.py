"""One smoke test drives a running server in headless Chromium (requirements S17.5)."""

import socket
import subprocess
import sys
import time

import httpx
import pytest

from moolakata.config import load
from moolakata.keys import cli as keys_cli
from moolakata.keys import phrase

pytestmark = pytest.mark.browser


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start(tmp, keyed: bool):
    """A server from this checkout, as the image runs it: with a keyring, locked; without,
    uninitialised (S15.4.4). Its base address, its process and its key (None without)."""
    port = free_port()
    config = tmp / "moolakata.toml"
    config.write_text(f"""
[server]
name = "smoke"
mode = "proxy"
host = "127.0.0.1"
port = {port}
[paths]
data = "{tmp / "data"}"
backups = "{tmp / "backups"}"
socket = "{tmp / "run" / "sock"}"
""")
    key = keys_cli.init(load(config), say=lambda _: None, confirm=False) if keyed else None
    log = open(tmp / "server.log", "wb")  # noqa: SIM115 - a file: an unread pipe fills up
    proc = subprocess.Popen(
        [sys.executable, "-m", "moolakata.main", "--config", str(config), "serve"],
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    base = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        try:
            r = httpx.get(base + "/healthz")
            if r.status_code == 503 and r.json()["status"] in ("locked", "uninitialised"):
                break
        except httpx.TransportError:
            pass
        if proc.poll() is not None:
            pytest.fail(f"server exited: {(tmp / 'server.log').read_text()}")
        time.sleep(0.1)
    return base, proc, key


def stop(proc) -> None:
    proc.terminate()  # SIGTERM: a clean stop within the 5-second grace (S13.6)
    assert proc.wait(timeout=8) == 0


@pytest.fixture(scope="module")
def running(tmp_path_factory):
    base, proc, key = start(tmp_path_factory.mktemp("smoke"), keyed=True)
    # It starts locked (S15.4.3): the phrase opens it, as the unlock page or `keys unlock` do.
    r = httpx.post(
        base + "/ui/api/unlock",
        json={"phrase": " ".join(phrase.to_words(key))},
        headers={"Origin": base},
        timeout=60,
    )
    assert r.status_code == 200, r.text
    assert httpx.get(base + "/healthz").status_code == 200
    yield base
    stop(proc)


@pytest.fixture(scope="module")
def browser():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


def open_page(browser, url):
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    problems = []
    page.on("pageerror", lambda e: problems.append(f"page error: {e}"))
    # The session check before signing in answers 401 by design; its "Failed to load resource"
    # carries no address, so failed responses are checked by address instead.
    page.on(
        "console",
        lambda m: (
            m.type == "error"
            and "Failed to load resource" not in m.text
            and problems.append(f"console: {m.text}")
        ),
    )
    page.on(
        "response",
        lambda r: (
            r.status >= 400
            and not r.url.endswith("/ui/api/session")
            and problems.append(f"{r.status} for {r.url}")
        ),
    )
    page.goto(url)
    return page, problems


def test_app_loads_under_its_csp(running, browser):
    page, problems = open_page(browser, running + "/ui/")
    page.wait_for_selector("#app > *")
    assert problems == []
    page.close()


def test_demo_runs_in_its_sandbox(running, browser):
    page, problems = open_page(browser, running + "/demo#/dashboard")
    page.wait_for_timeout(300)
    assert page.evaluate("typeof window.MOCK_INDEX") == "object"
    assert problems == []
    page.close()


def test_the_welcome_makes_the_key_and_the_first_admin(tmp_path, browser):
    """A new server, no keyring: the welcome in the browser shows a phrase, takes three of its
    words back, and sets up the first admin, who lands on the Dashboard (S12.14.1, S10.1.2)."""
    import re

    base, proc, _ = start(tmp_path, keyed=False)
    try:
        page, problems = open_page(browser, base + "/ui/")
        page.get_by_role("button", name="Show my recovery phrase").click()
        page.locator("ol.phrase").wait_for()
        words = page.locator("ol.phrase li").all_inner_texts()
        assert len(words) == 12 and phrase.from_words(words)
        page.get_by_role("button", name="I've written them down").click()
        page.get_by_role("button", name="Make the key").wait_for()
        asked = [
            int(re.search(r"\d+", label).group())
            for label in page.locator("label").all_inner_texts()
            if label.startswith("Word")
        ]
        for n in asked:
            page.locator(f"#x-word-{n}").fill(words[n - 1][:4])
        page.get_by_role("button", name="Make the key").click()
        page.get_by_text("Set up the admin account").wait_for(timeout=60000)
        assert httpx.get(base + "/healthz").status_code == 200
        page.locator("#f-your-name").fill("Pat Tester")
        page.locator("select").select_option("female")
        page.locator("#f-email-address").fill("pat@home.lan")
        page.locator("#f-password").fill("a long admin passphrase")
        page.get_by_role("button", name="Save and continue").click()
        page.get_by_role("heading", name="Dashboard").first.wait_for(timeout=30000)
        assert problems == []
        page.close()
    finally:
        stop(proc)
