"""The browser app against a seeded dev server in headless Chromium (requirements S17.5): every
screen, tab and dialog opens without a page or console error, has its guide, and each field's
label finds a heading in it, in the page's order (S12.7.6)."""

import re
import socket
import subprocess
import sys
import time
from collections import deque
from pathlib import Path

import httpx
import pytest

pytestmark = pytest.mark.browser

# A failed request shows in the console without its address; failed responses are checked by
# address instead, where the session check before signing in may answer 401.
LOAD_FAILED = re.compile(r"Failed to load resource")
EXPECTED_FAILURES = re.compile(r"/ui/api/session$")
# The API allows a session 600 requests a minute (S13.7.5); a test opens screens far faster
# than a person, so it keeps under that instead.
API_PER_MINUTE = 500
SETTINGS_SECTIONS = (
    "general",
    "email",
    "sessions",
    "signup",
    "passwords",
    "prices",
    "imports",
    "backups",
    "keys",
    "alerts",
)


# The dev server's data directory, where its emails are written.
DEV: dict[str, Path] = {}


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
    DEV["data"] = data
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
        pg.api_times = deque()
        pg.on("request", lambda r: "/ui/api/" in r.url and pg.api_times.append(time.monotonic()))
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
    pace(page)
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


def pace(page) -> None:
    """Wait while this session is near the API's limit."""
    times = page.api_times
    while times and time.monotonic() - times[0] > 60:
        times.popleft()
    if len(times) >= API_PER_MINUTE:
        page.wait_for_timeout(1000 * (61 - (time.monotonic() - times[0])))


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
        "/ui/alerts",
        "/ui/users",
        "/ui/profile",
    ]
    for t in ("checking", "brokerage", "401k", "credit-card"):
        for tab in ("overview", "holdings", "transactions", "reconcile", "sharing", "settings"):
            paths.append(f"/ui/accounts/{ids[t]}/{tab}")
    for p in ports:
        paths += [f"/ui/portfolios/{p}/performance", f"/ui/portfolios/{p}/holdings"]
    for s in SETTINGS_SECTIONS:
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
    page.wait_for_selector('.help [data-anchor="birth-year"]:not(.flash)')
    assert page.locator(".help h2.active").evaluate_all("hs => hs.map(h => h.dataset.anchor)") == [
        "birth-year"
    ]
    page.focus("#f-display-name")
    page.wait_for_selector('.help [data-anchor="display-name"].active')
    assert page.locator(".help h2.active").count() == 1
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


def test_every_password_field_has_an_eye_that_reveals_it(page):
    visit(page, "/ui/profile")
    fields = page.locator("input.in[type=password]")
    assert fields.count() == 2
    assert page.locator(".pw > input.in + button.icon-btn").count() == fields.count()
    page.fill("#f-current-password", "secret words")
    page.locator("#f-current-password + button").click()
    assert page.get_attribute("#f-current-password", "type") == "text"
    page.get_by_role("button", name="Hide password").click()
    assert page.get_attribute("#f-current-password", "type") == "password"
    assert page.input_value("#f-current-password") == "secret words"


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


def signed_in_page(page, username: str):
    """Another browser context, signed in as one of the seed users, watched like `page`."""
    ctx = page.context.browser.new_context(
        ignore_https_errors=True, viewport={"width": 1440, "height": 900}
    )
    pg = ctx.new_page()
    pg.problems, pg.api_times, pg.base = [], deque(), page.base
    pg.on("pageerror", lambda e: pg.problems.append(f"page error on {pg.url}: {e}"))
    pg.on(
        "console",
        lambda m: (
            m.type == "error"
            and not LOAD_FAILED.search(m.text)
            and pg.problems.append(f"console on {pg.url}: {m.text}")
        ),
    )
    pg.goto(page.base + "/ui/")
    pg.fill("#f-username-or-email", username)
    pg.fill("#f-password", "moneykata-dev")
    pg.click("button.btn.primary")
    return pg


def test_two_step_sign_in_through_the_app(page):
    """Turn it on in Profile, sign in with a recovery code, and an admin resets it (S10.1.6)."""
    from moneykata.auth import twostep

    bob = signed_in_page(page, "bob")
    bob.wait_for_selector(".side")
    visit(bob, "/ui/profile")
    bob.locator("#two-step").get_by_role("button", name="Turn on").click()
    bob.wait_for_selector(".dialog .qr img")
    wait_guide(bob, "dialog-two-step")
    check_guide(bob, ".dialog", "Turn on two-step sign-in")
    seed = bob.inner_text(".dialog code.key").replace(" ", "")
    bob.fill("#f-two-step-code", "000000")
    bob.locator(".dialog").get_by_role("button", name="Turn on").click()
    bob.wait_for_selector(".dialog .err")
    bob.fill("#f-two-step-code", twostep.code_at(seed, int(time.time()) // 30))
    bob.locator(".dialog").get_by_role("button", name="Turn on").click()
    bob.wait_for_selector(".dialog ul.codes")
    wait_guide(bob, "dialog-recovery-codes")
    codes = bob.locator(".dialog ul.codes code").all_inner_texts()
    assert len(codes) == 10
    bob.get_by_role("button", name="I've saved them").click()
    bob.wait_for_selector("#two-step .pill.ok")
    assert "10 recovery codes left" in bob.inner_text("#two-step")
    assert bob.problems == []
    bob.context.close()

    again = signed_in_page(page, "bob")
    again.wait_for_selector("text=Two-step sign-in")
    again.get_by_role("button", name="Use a recovery code").click()
    again.fill("#f-recovery-code", codes[3])
    again.get_by_role("button", name="Sign in", exact=True).click()
    again.wait_for_selector(".side")
    assert again.problems == []
    again.context.close()

    admin = signed_in_page(page, "admin")
    admin.wait_for_selector(".side")
    visit(admin, "/ui/users")
    row = admin.locator("tr", has_text="bob@")
    assert row.locator(".pill.ok", has_text="two-step").count() == 1
    row.get_by_role("button", name="Edit").click()
    admin.get_by_role("button", name="Reset two-step").click()
    admin.get_by_role("button", name="Turn it off").click()
    admin.wait_for_selector("text=Two-step sign-in is off for")
    row.locator(".pill.ok", has_text="two-step").wait_for(state="detached")
    assert admin.problems == []
    admin.context.close()


def last_mail_link() -> str:
    import email
    import email.policy

    newest = max((DEV["data"] / "mail").glob("*.eml"), key=lambda p: p.stat().st_mtime)
    msg = email.message_from_bytes(newest.read_bytes(), policy=email.policy.default)
    return re.search(r"https://\S+", msg.get_body().get_content()).group(0)


def test_sign_up_through_the_app(page):
    """Sign-up opened by an admin, asked for, confirmed and approved (S10.1.4)."""
    admin = signed_in_page(page, "admin")
    admin.wait_for_selector(".side")
    visit(admin, "/ui/settings/signup")
    admin.locator("#f-sign-up").click()
    admin.get_by_role("button", name="Save").click()
    admin.wait_for_selector("text=Saved")

    ctx = page.context.browser.new_context(
        ignore_https_errors=True, viewport={"width": 1440, "height": 900}
    )
    guest = ctx.new_page()
    guest.goto(page.base + "/ui/")
    guest.get_by_role("button", name="Sign up").click()
    guest.fill("#f-display-name", "Erin Shaw")
    guest.fill("#f-email", "erin@shaw.family")
    guest.fill("#f-username", "erin")
    guest.fill("#f-password", "a long passphrase for erin")
    guest.get_by_role("button", name="Ask for an account").click()
    guest.wait_for_selector("text=a link to confirm it is on its way")
    url = last_mail_link()
    assert "/ui/signup/confirm#" in url
    guest.goto(page.base + url[url.index("/ui/") :])
    guest.wait_for_selector("text=Waiting for approval")

    visit(admin, "/ui/users")
    req = admin.locator(".list-item", has_text="erin@shaw.family")
    req.get_by_role("button", name="Approve").click()
    admin.wait_for_selector("text=Erin Shaw can sign in now")
    assert admin.problems == []
    admin.context.close()

    guest.goto(page.base + "/ui/signin")
    guest.fill("#f-username-or-email", "erin")
    guest.fill("#f-password", "a long passphrase for erin")
    guest.get_by_role("button", name="Sign in", exact=True).click()
    guest.wait_for_selector(".side")
    ctx.close()
