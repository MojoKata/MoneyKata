"""Where the app's own files are: the server runs from the repository's layout, in a checkout
and in the image alike (/opt/moneykata mirrors it)."""

from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
WEB = PACKAGE.parents[2]
ROOT = WEB.parent
UI = WEB / "ui"
VERSION_FILE = WEB / "VERSION"
DEMO = ROOT / "docs" / "mockups" / "MoneyKata-mock.html"


def version() -> str:
    return VERSION_FILE.read_text().strip()
