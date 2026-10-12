"""The browser app against a seeded dev server in headless Chromium (requirements §20.5): every
screen, tab and dialog opens without a page or console error, has its guide, and each field's
label finds a heading in it, in the page's order (§15.7.6)."""

import re
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

pytestmark = pytest.mark.browser

# A failed request shows in the console without its address; failed responses are checked by
# address instead, where the session check before signing in may answer 401.
LOAD_FAILED = re.compile(r"Failed to load resource")
EXPECTED_FAILURES = re.compile(r"/ui/api/session$|/guides/shots/")


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def dev_server(tmp_path_factory):
    data = tmp_path_factory.mktemp("dev")
    port = free_port()
    log = open(data / "server.log", "wb")  # noqa: SIM115 - closed below
    # A file, not a pipe: a pipe nobody reads fills up and stops the server mid-request.
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "moneykata.main",
            "dev",
            "--seed",
            "--stubs",
            "--port",
            str(port),
            "--data",
            str(data),
        ],
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    base = f"https://127.0.0.1:{port}"
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        try:
            if httpx.get(base + "/healthz", verify=False).status_code == 200:
                break
        except httpx.TransportError:
            pass
        if proc.poll() is not None:
            pytest.fail("dev server exited: " + (data / "server.log").read_text())
        time.sleep(0.2)
    yield base
    proc.terminate()
    proc.wait(timeout=15)
    log.close()


@pytest.fixture(scope="module")
def page(dev_server):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(ignore_https_errors=True, viewport={"width": 1440, "height": 900})
        pg = ctx.new_page()
        pg.problems = []
        pg.on("pageerror", lambda e: pg.problems.append(f"page error on {pg.url}: {e}"))
        pg.on(
            "console",
            lambda m: (
                m.type == "error"
                and not LOAD_FAILED.search(m.text)
                and pg.problems.append(f"console on {pg.url}: {m.text}")
            ),
        )
        pg.on(
            "response",
            lambda r: (
                r.status >= 400
                and not EXPECTED_FAILURES.search(r.url)
                and pg.problems.append(f"{r.status} for {r.url}")
            ),
        )
        pg.goto(dev_server + "/ui/")
        pg.fill("#f-username-or-email", "alice")
        pg.fill("#f-password", "moneykata-dev")
        pg.click("button.btn.primary")
        pg.wait_for_selector(".side")
        pg.base = dev_server
        yield pg
        browser.close()


GUIDE_CHECK = """(scope) => {
  const root = document.querySelector(scope);
  const guide = document.querySelector('.help .guide');
  if (!root || !guide) return { error: 'no ' + (!root ? scope : 'help pane') };
  const anchors = [...guide.querySelectorAll('[data-anchor]')].map((h) => h.dataset.anchor);
  const fields = [...root.querySelectorAll('[id^="f-"], [data-help]')]
    .map((el) => el.dataset.help || el.id.slice(2))
    .filter((id, i, all) => all.indexOf(id) === i);
  const missing = fields.filter((f) => !anchors.includes(f));
  const order = fields.filter((f) => anchors.includes(f)).map((f) => anchors.indexOf(f));
  const backwards = order.findIndex((v, i) => i > 0 && v < order[i - 1]);
  return {
    key: guide.dataset.guide,
    missingGuide: guide.textContent.includes("guide is missing"),
    missing, fields,
    backwards: backwards < 0 ? null : fields.filter((f) => anchors.includes(f))[backwards],
  };
}"""


def check_guide(page, scope: str, where: str) -> None:
    page.wait_for_timeout(400)
    r = page.evaluate(GUIDE_CHECK, scope)
    assert "error" not in r, f"{where}: {r}"
    assert not r["missingGuide"], f"{where}: no guide {r['key']}"
    assert r["missing"] == [], f"{where} ({r['key']}): fields without a heading: {r['missing']}"
    assert r["backwards"] is None, f"{where} ({r['key']}): {r['backwards']} sends the guide up"


def visit(page, path: str) -> None:
    """Open a screen and wait until what it loads has arrived, as a person would, so the
    server isn't left with a queue of abandoned requests."""
    page.goto(page.base + path)
    try:
        page.wait_for_selector(".content > *", timeout=15000)
    except Exception:
        page.screenshot(path=str(Path(__file__).parent.parent / ".pytest_cache" / "stuck.png"))
        raise AssertionError(f"{path} drew nothing in 15 s") from None
    for _ in range(200):
        if not page.evaluate("document.querySelector('.content [aria-busy=\"true\"]')"):
            break
        page.wait_for_timeout(50)
    page.wait_for_timeout(300)


def account_ids(page) -> dict[str, str]:
    return page.evaluate("""async () => Object.fromEntries(
        (await (await fetch('/ui/api/accounts')).json())
        .map((a) => [a.type, a.id]))""")


def test_every_screen_and_tab_has_its_guide(page):
    ids = account_ids(page)
    ports = page.evaluate("""async () => (await (await fetch('/ui/api/portfolios')).json())
        .map((p) => p.id)""")
    paths = [
        "/ui/",
        "/ui/accounts",
        "/ui/transactions",
        "/ui/portfolios",
        "/ui/activity",
        "/ui/users",
        "/ui/profile",
    ]
    for t in ("checking", "brokerage", "401k", "credit-card"):
        for tab in ("overview", "holdings", "transactions", "reconcile", "sharing", "settings"):
            paths.append(f"/ui/accounts/{ids[t]}/{tab}")
    for p in ports:
        paths += [f"/ui/portfolios/{p}/performance", f"/ui/portfolios/{p}/holdings"]
    for s in ("general", "sessions", "passwords", "prices", "imports", "backups", "keys"):
        paths.append(f"/ui/settings/{s}")
    for path in paths:
        visit(page, path)
        check_guide(page, ".content", path)
    assert page.problems == []


def wait_guide(page, key: str) -> None:
    """Wait for the help pane to show a guide. Polled from outside the page: a string
    evaluated inside it is refused by the app's CSP, which is the point."""
    for _ in range(100):
        if page.evaluate("document.querySelector('.help .guide')?.dataset.guide") == key:
            return
        page.wait_for_timeout(50)
    raise AssertionError(f"the help pane never showed {key}")


def open_dialog(page, path: str, button: str, guide: str) -> None:
    assert page.problems == [], page.problems
    visit(page, path)
    page.get_by_role("button", name=button).first.click()
    page.wait_for_selector(".dialog")
    wait_guide(page, guide)
    check_guide(page, ".dialog", f"{path} › {button}")


def close_dialog(page) -> None:
    page.keyboard.press("Escape")
    page.wait_for_selector(".dialog", state="detached")


def test_every_dialog_has_its_guide(page):
    ids = account_ids(page)
    for path, button, guide in (
        ("/ui/accounts", "New account", "dialog-new-account"),
        ("/ui/accounts", "Import", "dialog-import"),
        ("/ui/accounts", "Share Everyday checking", "dialog-share"),
        ("/ui/transactions", "Add", "dialog-transaction"),
        (
            f"/ui/accounts/{ids['checking']}/reconcile",
            "Type today's balance",
            "dialog-type-balance",
        ),
        (
            f"/ui/accounts/{ids['checking']}/reconcile",
            "Tick off against a statement",
            "dialog-tick-off",
        ),
        ("/ui/portfolios", "New portfolio", "dialog-portfolio"),
        ("/ui/users", "New user", "dialog-new-user"),
        ("/ui/users", "New group", "dialog-group"),
        ("/ui/settings/prices", "Add a source", "dialog-add-source"),
    ):
        open_dialog(page, path, button, guide)
        close_dialog(page)
    # The type picker leads to the form.
    open_dialog(page, "/ui/accounts", "New account", "dialog-new-account")
    page.get_by_role("button", name=re.compile("^Brokerage")).click()
    wait_guide(page, "dialog-account-form")
    check_guide(page, ".dialog", "the account form")
    close_dialog(page)
    # Splits add rows that name their heading.
    open_dialog(page, "/ui/transactions", "Add", "dialog-transaction")
    page.select_option(".dialog #f-account", label="Everyday checking")
    page.get_by_role("button", name="Split…").click()
    check_guide(page, ".dialog", "a split transaction")
    close_dialog(page)
    assert page.problems == []


def test_the_help_pane_follows_the_focus_and_f1_toggles_it(page):
    visit(page, "/ui/profile")
    page.focus("#f-birth-year")
    page.wait_for_selector('.help [data-anchor="birth-year"].flash')
    page.keyboard.press("F1")
    page.wait_for_selector(".help", state="detached")
    assert page.is_visible(".help-corner")
    page.keyboard.press("F1")
    page.wait_for_selector(".help")


def test_privacy_mode_blurs_amounts(page):
    visit(page, "/ui/accounts")
    page.get_by_role("button", name="Hide amounts (privacy mode)").click()
    page.wait_for_selector("body.privacy")
    blur = page.evaluate("getComputedStyle(document.querySelector('.amt')).filter")
    assert "blur" in blur
    page.get_by_role("button", name="Show amounts").click()


def test_categorise_and_share_through_the_app(page):
    visit(page, "/ui/transactions?category=none")
    page.wait_for_selector("tbody input[type=checkbox]")
    boxes = page.query_selector_all("tbody input[type=checkbox]:not([disabled])")
    boxes[0].check()
    boxes[1].check()
    page.select_option("#f-categorise-as", label="Food › Groceries")
    page.get_by_role("button", name="Categorise", exact=True).click()
    page.wait_for_selector("text=2 transactions categorised")
    visit(page, "/ui/accounts")
    page.get_by_role("button", name="Share Taxable brokerage").click()
    page.wait_for_selector(".dialog .seg")
    page.get_by_role("radio", name="Read").first.click()
    page.get_by_role("button", name="Save").click()
    page.wait_for_selector("text=Sharing saved")
    assert page.problems == []
