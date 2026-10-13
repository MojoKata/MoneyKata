"""One smoke test drives a running server in headless Chromium (requirements S17.5)."""

import socket
import subprocess
import sys
import time

import httpx
import pytest

from moneykata.config import load
from moneykata.keys import cli as keys_cli

pytestmark = pytest.mark.browser


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def running(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("smoke")
    port = free_port()
    config = tmp / "moneykata.toml"
    config.write_text(f"""
[server]
name = "smoke"
mode = "proxy"
host = "127.0.0.1"
port = {port}
[paths]
data = "{tmp / "data"}"
backups = "{tmp / "backups"}"
[keys]
master = "{tmp / "keys" / "master.key"}"
""")
    keys_cli.init(load(config), say=lambda _: None, confirm=False)
    log = open(tmp / "server.log", "wb")  # noqa: SIM115 - a file: an unread pipe fills up
    proc = subprocess.Popen(
        [sys.executable, "-m", "moneykata.main", "--config", str(config), "serve"],
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    base = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        try:
            if httpx.get(base + "/healthz").status_code == 200:
                break
        except httpx.TransportError:
            pass
        if proc.poll() is not None:
            pytest.fail(f"server exited: {(tmp / 'server.log').read_text()}")
        time.sleep(0.1)
    yield base
    proc.terminate()  # SIGTERM: a clean stop within the 5-second grace (S13.6)
    assert proc.wait(timeout=8) == 0


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
