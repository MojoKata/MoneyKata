"""The Folder driver (requirements S18.9.1): a folder on the connector's host, mounted read only
(a Downloads folder), watched for statements and exports. Each file that appears is posted to
the account its rule names, by the file's name and the account's last four digits:
`umb-*.pdf → 3311`. No credentials, no hosts: downloading stays by hand, uploading doesn't."""

import fnmatch
import json
import re
from pathlib import Path

from . import Account, Driver, File, Result

RULE = re.compile(r"^\s*(?P<pattern>\S+)\s*(?:→|->)\s*(?P<last4>\d{4})\s*$")
EXTENSIONS = {".ofx": "ofx", ".qfx": "ofx", ".csv": "csv", ".pdf": "statement"}
MAX_BYTES = 25 * 1024 * 1024


def parse_rules(rules: list[str]) -> list[tuple[str, str]]:
    out = []
    for r in rules:
        m = RULE.match(r)
        if m:
            out.append((m["pattern"].lower(), m["last4"]))
    return out


class Folder(Driver):
    name = "folder"
    hosts = ()
    needs = ()
    interval = 5 * 60

    def __init__(self, posted: Path | None = None):
        # What was posted already, by name, size and time, so a file is posted once (and
        # MoneyKata's import is idempotent besides).
        self.posted_path = posted
        self._posted: dict[str, list] = self._load()

    def _load(self) -> dict[str, list]:
        try:
            return json.loads(self.posted_path.read_text()) if self.posted_path else {}
        except OSError, ValueError:
            return {}

    def _save(self) -> None:
        if self.posted_path:
            self.posted_path.write_text(json.dumps(self._posted))

    def run(
        self, settings: dict, credentials: dict | None, accounts: list[Account], http
    ) -> Result:
        folder = Path(str(settings.get("path") or ""))
        rules = parse_rules(settings.get("rules") or [])
        if not folder.is_dir():
            return Result("failing", f"the folder {folder} isn't there, or isn't mounted")
        by_last4 = {a.last4: a for a in accounts if a.last4}
        files: list[File] = []
        waiting = 0
        for path in sorted(folder.iterdir()):
            if not path.is_file() or path.name.startswith("."):
                continue
            fmt = EXTENSIONS.get(path.suffix.lower())
            if fmt is None:
                continue
            last4 = next((l4 for pat, l4 in rules if fnmatch.fnmatch(path.name.lower(), pat)), None)
            account = by_last4.get(last4) if last4 else None
            if account is None:
                waiting += 1
                continue
            st = path.stat()
            stamp = [st.st_size, int(st.st_mtime)]
            key = f"{folder}/{path.name}"
            if self._posted.get(key) == stamp or st.st_size > MAX_BYTES:
                continue
            files.append(File(account.id, path.name, path.read_bytes(), fmt))
            self._posted[key] = stamp
        self._save()
        message = f"{len(files)} new" if files else "nothing new"
        if waiting:
            message += f" · {waiting} file{'s' if waiting > 1 else ''} with no rule"
        return Result("ok", message, files=files)

    def unpost(self, folder: str, name: str) -> None:
        """A post refused for a limit: the file is posted again on a later run (S18.8)."""
        self._posted.pop(f"{folder}/{name}", None)
        self._save()
