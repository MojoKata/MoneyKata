"""Builds docs/mockups/MoneyKata-app.html, the mockup generated from the app (requirements S12.9).

A seeded dev server runs on a fixed day with repeatable ids. Headless Chromium signs in as each
sample user and opens every screen, tab, range and dialog; each answer the app asks the API for
is recorded. The page that comes out holds the app's own modules, styles and icons, the guides
and those answers, with a small backend in the page that serves them, so it opens from disk
and sends nothing anywhere.

    python web/ui/mockup/build.py           write the file
    python web/ui/mockup/build.py --check   fail if the file is not what the app makes now
"""

import argparse
import base64
import difflib
import itertools
import json
import re
import socket
import subprocess
import sys
import tempfile
import time
from collections import deque
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit

import httpx

from moneykata import exactjson

UI = Path(__file__).resolve().parents[1]
ROOT = UI.parents[1]
OUT = ROOT / "docs" / "mockups" / "MoneyKata-app.html"
# The day the sample data is shown on: the seed's year ends here.
AT = "2026-10-12T16:00:00+00:00"
SHOWN_DIR = "/srv/moneykata"
PASSWORD = "moneykata-dev"  # noqa: S105 - dev mode's seed users
USERS = ("alice", "bob", "admin")
# The API allows a session 600 requests a minute (requirements S13.7.5); the crawl keeps under it.
API_PER_MINUTE = 500
# The app's source, as the browser loads it; mockup/ adds the router and the MOCK pill's menu.
SOURCE_DIRS = ("app", "api", "store", "components", "screens", "charts", "account-types")
SETTINGS = (
    "general",
    "email",
    "sessions",
    "signup",
    "passwords",
    "prices",
    "bitcoin",
    "links",
    "imports",
    "receipts",
    "tax-tables",
    "backups",
    "storage",
    "keys",
    "alerts",
)
# (path, button, guide): the dialogs that load something when they open.
DIALOGS = (
    ("/ui/accounts", "New account", "dialog-new-account"),
    ("/ui/accounts", "Import", "dialog-import"),
    ("/ui/transactions", "Add", "dialog-transaction"),
    ("/ui/portfolios", "New portfolio", "dialog-portfolio"),
    ("/ui/budgets", "New budget", "dialog-budget"),
    ("/ui/budgets", "Edit plan", "dialog-plan"),
    ("/ui/receipts", "Receipt Blue Bottle Coffee", "dialog-receipt"),
    ("/ui/projections", "New projection", "dialog-new-projection"),
    ("/ui/gifts/people", "Add a person", "dialog-person"),
    ("/ui/gifts/gifts", "Add a gift", "dialog-gift"),
    ("/ui/giving/donations", "Record a donation", "dialog-donation"),
    ("/ui/positions/open", "Record an option trade", "dialog-option-trade"),
    ("/ui/positions/strategies", "An underlying was adjusted…", "dialog-option-adjust"),
    ("/ui/giving/organisations", "Add an organisation", "dialog-organisation"),
    ("/ui/taxes/summary", "New tax book", "dialog-tax-book"),
    ("/ui/taxes/filings", "Add a filing", "dialog-filing"),
    ("/ui/profile", "Compare models", "dialog-bitcoin-models"),
    ("/ui/profile", "New token", "dialog-new-token"),
    ("/ui/users", "New user", "dialog-new-user"),
    ("/ui/users", "New group", "dialog-group"),
    ("/ui/settings/prices", "Add a source", "dialog-add-source"),
    ("/ui/settings/links", "Enter a link code", "dialog-link-join"),
)
# POSTs that only work something out: the first answer is kept, for the page to show.
COMPUTED = re.compile(r"/ui/api/accounts/[^/]+/loan/(payoff|split)$")
IMPORTS = re.compile(r"""(\bfrom\s*|\bimport\s*\(?\s*)(['"])(\.{1,2}/[^'"]+)\2""")
SCREENS = re.compile(r"import\(`\.\./screens/\$\{name\}\.js`\)")


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Server:
    """moneykata dev, seeded, on the stub prices, frozen on AT."""

    def __init__(self, data: Path) -> None:
        self.port = free_port()
        self.base = f"https://127.0.0.1:{self.port}"
        self.log_path = data / "server.log"
        self.log = open(self.log_path, "wb")  # noqa: SIM115 - closed in stop()
        self.proc = subprocess.Popen(  # noqa: S603 - this checkout's own server
            [
                sys.executable,
                "-m",
                "moneykata.main",
                "dev",
                "--seed",
                "--stubs",
                "--frozen",
                AT,
                "--port",
                str(self.port),
                "--data",
                str(data),
            ],
            stdout=self.log,
            stderr=subprocess.STDOUT,
        )
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            try:
                if httpx.get(self.base + "/healthz", verify=False).status_code == 200:  # noqa: S501
                    return
            except httpx.TransportError:
                pass
            if self.proc.poll() is not None:
                break
            time.sleep(0.2)
        self.stop()
        sys.exit("the dev server did not start:\n" + self.log_path.read_text())

    def stop(self) -> None:
        if self.proc.poll() is None:
            self.proc.terminate()
            self.proc.wait(timeout=15)
        self.log.close()


def key_of(url: str) -> str:
    """A request's key, as the page's backend makes it: the path and the sorted query, less
    `since`, which only says "now"."""
    u = urlsplit(url)
    q = sorted((k, v) for k, v in parse_qsl(u.query, keep_blank_values=True) if k != "since")
    return u.path + ("?" + urlencode(q, safe="*") if q else "")


class Recorder:
    """Signs in as one user and records every answer the app's GETs receive."""

    def __init__(self, browser, base: str, username: str, data: str) -> None:
        self.base = base
        self.data = data
        self.username = username
        self.ctx = browser.new_context(
            ignore_https_errors=True,
            viewport={"width": 1440, "height": 900},
            timezone_id="America/New_York",
            locale="en-US",
        )
        self.page = self.ctx.new_page()
        self.page.clock.set_fixed_time(AT)
        self.answers: dict[str, dict] = {}
        self.sent: deque[float] = deque()
        self.ctx.route("**/ui/api/**", self.through)
        self.page.goto(base + "/ui/")
        self.page.fill("#f-username-or-email", username)
        self.page.fill("#f-password", PASSWORD)
        self.page.click("button.btn.primary")
        self.page.wait_for_selector(".side")
        self.settle()

    def settle(self) -> None:
        for _ in range(300):
            if not self.page.evaluate("!!document.querySelector('[aria-busy=\"true\"]')"):
                break
            self.page.wait_for_timeout(50)
        self.page.wait_for_timeout(250)

    def pace(self) -> None:
        """Hold a request while the session is near the API's limit."""
        while self.sent and time.monotonic() - self.sent[0] > 60:
            self.sent.popleft()
        if len(self.sent) >= API_PER_MINUTE:
            time.sleep(61 - (time.monotonic() - self.sent[0]))
        self.sent.append(time.monotonic())

    def through(self, route) -> None:
        """Pass each request to the server, keeping what a GET was answered."""
        req = route.request
        if req.url.endswith("/events"):
            # No stream while crawling: one left open by each page fills the browser's
            # connections. A 204 tells EventSource not to try again.
            route.fulfill(status=204)
            return
        self.pace()
        if req.method == "POST" and COMPUTED.search(key_of(req.url)):
            r = route.fetch()
            self.answers.setdefault(
                "POST " + key_of(req.url), {"status": r.status, "body": exactjson.loads(r.text())}
            )
            route.fulfill(response=r)
            return
        if req.method != "GET":
            route.fallback()
            return
        r = route.fetch()
        kind = r.headers.get("content-type", "")
        if not kind.startswith("application/json") and r.status == 200 and r.body():
            # A picture (a receipt's thumbnail): kept as it came, for the page's fetch.
            self.answers["GET " + key_of(req.url)] = {
                "status": r.status,
                "type": kind,
                "binary": base64.b64encode(r.body()).decode(),
            }
            route.fulfill(response=r)
            return
        # Where this run kept its data is a temporary directory; the mockup shows a fixed one.
        text = r.text().replace(self.data, SHOWN_DIR)
        self.answers["GET " + key_of(req.url)] = {
            "status": r.status,
            "body": exactjson.loads(text) if text else None,
        }
        route.fulfill(response=r, body=text)

    def visit(self, path: str) -> None:
        self.page.goto(self.base + path)
        try:
            self.page.wait_for_selector(".content > *", timeout=20000)
        except Exception:
            sys.exit(f"{path} drew nothing in 20 s for {self.username}")
        self.settle()
        # Every range and chip a screen offers.
        chips = self.page.locator(".content .chips button")
        for i in range(chips.count()):
            chips.nth(i).click()
            self.settle()

    def api(self, path: str):
        return self.page.evaluate(f"async () => (await fetch('/ui/api{path}')).json()")

    def dialog(self, path: str, button: str) -> None:
        self.visit(path)
        target = self.page.get_by_role("button", name=button).first
        if not target.count() or not target.is_enabled():
            return
        target.click()
        self.page.wait_for_selector(".dialog")
        self.settle()
        self.page.keyboard.press("Escape")
        self.page.wait_for_selector(".dialog", state="detached")

    def hello(self) -> dict:
        self.ctx.unroute_all()
        return self.page.evaluate("""() => new Promise((done) => {
            const s = new EventSource('/ui/api/events');
            s.addEventListener('hello', (e) => { s.close(); done(JSON.parse(e.data)); });
        })""")

    def crawl(self) -> None:
        session = self.api("/session")
        admin = session["user"]["admin"]
        paths = [
            "/ui/",
            "/ui/accounts",
            "/ui/transactions",
            "/ui/portfolios",
            "/ui/positions/open",
            "/ui/positions/strategies",
            "/ui/positions/closed",
            "/ui/positions/trades",
            "/ui/positions/gains",
            "/ui/activity",
            "/ui/alerts",
            "/ui/receipts",
            "/ui/projections",
            "/ui/gifts/upcoming",
            "/ui/gifts/people",
            "/ui/gifts/gifts",
            "/ui/gifts/spending",
            "/ui/giving/overview",
            "/ui/giving/donations",
            "/ui/giving/organisations",
            "/ui/giving/fund",
            "/ui/taxes/summary",
            "/ui/taxes/filings",
            "/ui/taxes/documents",
            "/ui/taxes/gains",
            "/ui/taxes/income",
            "/ui/taxes/retirement",
            "/ui/taxes/deductions",
            "/ui/taxes/giving",
            "/ui/taxes/education",
            "/ui/taxes/property",
            "/ui/taxes/issues",
        ]
        for x in self.api("/projections")["items"]:
            paths.append(f"/ui/projections/{x['id']}")
        for b in self.api("/budgets")["items"]:
            paths += [
                f"/ui/budgets/{b['id']}/{t}" for t in ("month", "cash-flow", "trends", "recurring")
            ]
        paths += ["/ui/profile", "/ui/transactions?category=none"]
        if admin:
            paths += ["/ui/users"] + [f"/ui/settings/{s}" for s in SETTINGS]
        for p in paths:
            self.visit(p)
        for a in self.api("/accounts")["items"]:
            self.visit(f"/ui/accounts/{a['id']}")
            tabs = self.page.eval_on_selector_all(
                ".content .tabs a", "(links) => links.map((l) => l.getAttribute('href'))"
            )
            for t in tabs:
                self.visit(t)
            if a["level"] != "read":
                self.dialog(f"/ui/accounts/{a['id']}/reconcile", "Type today's balance")
                self.dialog(f"/ui/accounts/{a['id']}/reconcile", "Tick off against a statement")
                self.dialog(f"/ui/accounts/{a['id']}", "Record a payment")
            self.dialog("/ui/accounts", f"Share {a['name']}")
        for p in self.api("/portfolios")["items"]:
            for tab in ("performance", "holdings", "projections"):
                self.visit(f"/ui/portfolios/{p['id']}/{tab}")
        for path, button, _ in DIALOGS:
            if admin or not path.startswith(("/ui/users", "/ui/settings")):
                self.dialog(path, button)
        self.settle()

    def close(self) -> None:
        self.ctx.close()


def record() -> tuple[dict, dict, list]:
    from playwright.sync_api import sync_playwright

    answers, hellos, users = {}, {}, []
    with tempfile.TemporaryDirectory(prefix="mk-mockup-") as tmp:
        server = Server(Path(tmp))
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                for username in USERS:
                    r = Recorder(browser, server.base, username, tmp)
                    r.crawl()
                    answers[username] = dict(sorted(r.answers.items()))
                    hellos[username] = r.hello()
                    me = r.answers["GET /ui/api/session"]["body"]["user"]
                    users.append({"username": username, "name": me["displayName"]})
                    r.close()
                browser.close()
        finally:
            server.stop()
    return answers, hellos, users


def specifier(path: Path) -> str:
    return "@mk/" + path.relative_to(UI).as_posix()


def data_url(text: str, mime: str = "text/javascript") -> str:
    return f"data:{mime};charset=utf-8;base64," + base64.b64encode(text.encode()).decode()


def modules(bare: dict[str, Path]) -> dict[str, str]:
    """Every module the app can load, under a name of its own, with its relative imports
    rewritten to those names: a module loaded from a data: address has nothing to be
    relative to."""
    todo = [p for d in SOURCE_DIRS for p in sorted((UI / d).rglob("*.js"))]
    todo += [UI / "mockup" / "iso.js", UI / "mockup" / "menu.js", *bare.values()]
    out: dict[str, str] = {}
    while todo:
        path = todo.pop()
        name = specifier(path)
        if name in out:
            continue
        text = path.read_text()

        def rewrite(m: re.Match, path=path) -> str:
            target = (path.parent / m.group(3)).resolve()
            if target.suffix not in (".js", ".mjs") or not target.is_file():
                return m.group(0)
            todo.append(target)
            return f"{m.group(1)}{m.group(2)}{specifier(target)}{m.group(2)}"

        text = IMPORTS.sub(rewrite, text)
        text = SCREENS.sub("import(`@mk/screens/${name}.js`)", text)
        out[name] = text
    return out


def embed(name: str, text: str) -> str:
    """A module's source, which sits in a <script> element as it is: it may not hold what
    would end that element early."""
    if re.search(r"</script|<!--", text, re.I):
        sys.exit(f"{name} holds </script or <!--, which the mockup cannot embed")
    return text


def lines(data: dict) -> str:
    """The recorded data as JSON with one answer, guide or user per line, so a change to the
    app shows in a diff as the lines it changed."""
    out = []
    for k in sorted(data):
        v = data[k]
        if isinstance(v, dict) and k in ("api", "events", "guides"):
            inner = []
            for k2 in sorted(v):
                v2 = v[k2]
                if k == "api":
                    rows = ",\n".join(
                        json.dumps(k3)
                        + ":"
                        + exactjson.dumps(v2[k3], sort_keys=True, ensure_ascii=False)
                        for k3 in sorted(v2)
                    )
                    inner.append(f"{json.dumps(k2)}:{{\n{rows}\n}}")
                else:
                    inner.append(
                        f"{json.dumps(k2)}:{json.dumps(v2, sort_keys=True, ensure_ascii=False)}"
                    )
            out.append(f"{json.dumps(k)}:{{\n" + ",\n".join(inner) + "\n}")
        else:
            out.append(f"{json.dumps(k)}:{json.dumps(v, sort_keys=True, ensure_ascii=False)}")
    return "{\n" + ",\n".join(out) + "\n}"


def assemble(answers: dict, hellos: dict, users: list) -> str:
    version = (ROOT / "web" / "VERSION").read_text().strip()
    page = (UI / "index.html").read_text()
    prefix = f"/ui/v/{version}/"
    page = page.replace("{{version}}", version).replace("{{dev}}", "0")
    page = page.replace(' nonce="{{nonce}}"', "")

    m = re.search(r'<script type="importmap">\s*(\{.*?\})\s*</script>', page, re.S)
    assert m, "index.html has no import map"
    bare = {k: UI / v.removeprefix(prefix) for k, v in json.loads(m.group(1))["imports"].items()}
    code = modules(bare)
    # The bare names point at modules by their own names; preact-iso is the mockup's router,
    # which loads the real one as @mk/preact-iso.
    aliases = {k: specifier(p) for k, p in sorted(bare.items())}
    aliases["@mk/preact-iso"] = aliases["preact-iso"]
    aliases["preact-iso"] = "@mk/mockup/iso.js"
    scripts = "".join(
        f'<script type="text/plain" data-module="{name}">\n{embed(name, code[name])}</script>\n'
        for name in sorted(code)
    )

    css = "\n".join(
        (UI / "styles" / f"{n}.css").read_text() for n in ("tokens", "base", "components")
    )
    sprite = (UI / "assets" / "icons.svg").read_text()
    sprite = re.sub(r"<\?xml.*?\?>\s*", "", sprite)
    sprite = sprite.replace(
        "<svg ",
        '<svg id="mk-icons" aria-hidden="true" style="position:absolute;width:0;height:0" ',
        1,
    )
    favicon = data_url((UI / "assets" / "favicon.svg").read_text(), "image/svg+xml")
    guides = {p.stem: p.read_text() for p in sorted((UI / "guides").glob("*.md"))}
    data = {
        "now": AT,
        "users": users,
        "api": answers,
        "events": hellos,
        "guides": guides,
        "aliases": aliases,
        "main": "@mk/app/main.js",
    }
    # JSON with no "<", which could end its <script> element early.
    blob = lines(data).replace("<", "\\u003c")
    runtime = (UI / "mockup" / "runtime.js").read_text()

    page = re.sub(r'<link rel="stylesheet"[^>]*>\n', "", page)
    page = re.sub(r'(<link rel="icon" href=")[^"]*', lambda m: m.group(1) + favicon, page)
    page = page.replace(
        '<meta name="mk-dev" content="0">',
        '<meta name="mk-dev" content="0">\n<meta name="mk-mockup" content="1">\n'
        '<meta name="mk-guides" content="../../web/ui/guides">',
    )
    # The page's runtime makes the import map from the modules below and then starts the app.
    page = page.replace(m.group(0) + "\n", "")
    page = re.sub(r'<script type="module" src="[^"]*main\.js"></script>\n', "", page)
    page = page.replace(
        "<title>MoneyKata</title>",
        "<title>MoneyKata</title>\n"
        "<!-- Generated by web/ui/mockup/build.py from the app (requirements S12.9). Do not edit:"
        " run web/dev.sh mockup. -->\n"
        f"<style>\n{css}</style>",
    )
    page = page.replace(
        '<div id="app"></div>\n',
        f'{sprite.strip()}\n<div id="app"></div>\n'
        f'<script type="application/json" id="mk-data">\n{blob}\n</script>\n'
        f"{scripts}<script>\n{embed('runtime.js', runtime)}</script>\n",
    )
    return page


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--check", action="store_true", help="fail if the file is out of date")
    args = p.parse_args(argv)
    html = assemble(*record())
    if args.check:
        now = OUT.read_text() if OUT.exists() else ""
        if now != html:
            diff = difflib.unified_diff(now.splitlines(), html.splitlines(), lineterm="", n=0)
            for line in itertools.islice(diff, 2, 22):
                print(line[:200], file=sys.stderr)
            print(f"{OUT.relative_to(ROOT)} is out of date: run web/dev.sh mockup", file=sys.stderr)
            return 1
        return 0
    OUT.write_text(html)
    print(f"wrote {OUT.relative_to(ROOT)} ({len(html.encode()) // 1024} KiB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
