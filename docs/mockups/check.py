"""Open every screen, tab, Settings section and dialog of the mockup and fail on any error.

    python docs/mockups/check.py shots/

Needs Playwright for Python and its Chromium (`pip install playwright`, then
`playwright install chromium`). The screens, dialogs and Settings sections come from the
mockup itself (`window.MOCK_INDEX`), so nothing here needs updating when one is added.
Screenshots of each go to the directory given. The mockup draws at `zoom: 2`, so the
viewport is 2880x1800, which shows what a 1440x900 window does.
"""

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

MOCKUP = Path(__file__).resolve().parent / "MoolaKata-mock.html"
VIEWPORT = {"width": 2880, "height": 1800}


def main(out: Path) -> int:
    out.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    url = MOCKUP.as_uri()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport=VIEWPORT)
        page.on("pageerror", lambda e: errors.append(f"page error: {e}"))
        page.on("console", lambda m: m.type == "error" and errors.append(f"console: {m.text}"))
        page.goto(url + "#/dashboard")
        page.wait_for_timeout(200)
        index = page.evaluate("window.MOCK_INDEX")
        shots = 0

        def shot(name: str) -> None:
            nonlocal shots
            page.screenshot(path=str(out / f"{name}.png"))
            shots += 1

        def missing_help(where: str, scope: str) -> None:
            missing = page.evaluate(
                f"[...document.querySelectorAll('{scope} [id^=f-]')].map(e => e.id.slice(2))"
                ".filter(i => !document.getElementById('h-' + i))"
            )
            if missing:
                errors.append(f"{where}: fields without a help heading: {missing}")

        for locked in (False, True):
            page.evaluate(f"state.locked = {str(locked).lower()}")
            for screen in index["screens"]:
                if locked and not screen.startswith("linked"):
                    continue
                tag = screen.replace("/", "_") + ("-locked" if locked else "")
                page.evaluate(f"state.signedOut = false; location.hash = '#/{screen}'")
                page.wait_for_timeout(120)
                shot(tag)
                missing_help(screen, "main")
                for tab in page.query_selector_all(".tab"):
                    key, value = tab.get_attribute("data-k"), tab.get_attribute("data-v")
                    page.evaluate(f"state.tabs[{key!r}] = {value!r}; render()")
                    page.wait_for_timeout(60)
                    shot(f"{tag}-{value.split(' ')[0].lower()}")
                    missing_help(f"{screen} › {value}", "main")

        page.evaluate("state.locked = true; location.hash = '#/settings'")
        page.wait_for_timeout(120)
        for section in index["settings"]:
            page.evaluate(f"state.settings = {section!r}; render()")
            page.wait_for_timeout(60)
            shot(f"settings-{section}")
            missing_help(f"settings › {section}", "main")

        page.evaluate("location.hash = '#/dashboard'")
        page.wait_for_timeout(120)
        for dialog in index["dialogs"]:
            page.evaluate(f"showDialog({dialog!r}, {{}})")
            page.wait_for_timeout(80)
            shot(f"dialog-{dialog}")
            missing_help(f"dialog {dialog}", ".dialog")
            page.evaluate("closeDialog()")

        page.evaluate("state.theme = 'light'; location.hash = '#/dashboard'; render()")
        page.wait_for_timeout(120)
        shot("dashboard-light")
        browser.close()

    print(f"{shots} screenshots in {out}")
    if errors:
        print("\n".join(errors))
        return 1
    print("NO ERRORS")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(Path(sys.argv[1])))
