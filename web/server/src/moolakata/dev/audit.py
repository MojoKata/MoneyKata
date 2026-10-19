"""The egress audit (requirements S17.2.1, docs/dependencies.md): every change to the Python
lock or the vendor manifest is followed by a scan of what the installed wheels and the
vendored files could reach (URLs and the words of telemetry and update checks), diffed
against what the register last accepted, and by a run of the server with no network
(tests/test_no_network.py under `unshare -U -n`). `web/audit.json` records what was accepted
and the hashes of the files it was audited against; `web/check` only checks those still
match, which costs nothing.

    python -m moolakata.dev.audit scan      what each package could reach, and what is new
    python -m moolakata.dev.audit accept    record the scan and the files' hashes as audited
    python -m moolakata.dev.audit check     the hashes still match (what web/check runs)
"""

import hashlib
import json
import re
import sys
from importlib import metadata
from pathlib import Path

from .. import paths

AUDIT = paths.WEB / "audit.json"
LOCK = paths.WEB / "server" / "uv.lock"
MANIFEST = paths.UI / "vendor" / "manifest.json"
URL = re.compile(rb"https?://[A-Za-z0-9][A-Za-z0-9.-]+\.[A-Za-z]{2,}")
WORDS = re.compile(rb"telemetry|analytics|crash[_ -]?report|check[_ -]?for[_ -]?update", re.I)
SKIP = re.compile(r"\.(dist-info|egg-info)$|/(tests?|testing|__pycache__)/|\.pyc$")
# Hosts every library names for its own documentation or licence: not an endpoint.
NOISE = re.compile(
    r"(^|\.)(w3\.org|github\.com|githubusercontent\.com|readthedocs\.io|python\.org|pypi\.org|"
    r"example\.(com|org|net)|localhost|mozilla\.org|apache\.org|opensource\.org|gnu\.org|"
    r"creativecommons\.org|json\.org|ietf\.org|iana\.org|unicode\.org|wikipedia\.org|"
    r"schema\.org|xml\.org|npmjs\.com|nodejs\.org|yarnpkg\.com|stackoverflow\.com|"
    r"microsoft\.com/typescript|sourceforge\.net|gitlab\.com|bitbucket\.org|openssl\.org|"
    r"ecma-international\.org|whatwg\.org|json-schema\.org|jsdelivr\.net|unpkg\.com|"
    r"developer\.mozilla\.org|docs\.rs|crates\.io|rust-lang\.org|llvm\.org|gcc\.gnu\.org|"
    r"cloudflare\.com|google\.com|googleapis\.com|googlesource\.com|chromium\.org|"
    r"preactjs\.com|echarts\.apache\.org|zlib\.net|libpng\.org|sqlite\.org|zetetic\.net)$"
)


def _hash(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _scan_file(path: Path) -> tuple[set[str], bool]:
    try:
        data = path.read_bytes()
    except OSError:
        return set(), False
    hosts = set()
    for m in URL.findall(data):
        host = m.decode("latin-1").split("://", 1)[1].lower()
        if not NOISE.search(host):
            hosts.add(host)
    return hosts, bool(WORDS.search(data))


def _scan_tree(root: Path) -> tuple[set[str], list[str]]:
    hosts, words = set(), []
    for p in root.rglob("*"):
        if not p.is_file() or SKIP.search(str(p)):
            continue
        if p.suffix not in (
            ".py",
            ".so",
            ".pyd",
            ".js",
            ".mjs",
            ".json",
            ".txt",
            ".yaml",
            ".yml",
            "",
        ):
            continue
        h, w = _scan_file(p)
        hosts |= h
        if w:
            words.append(str(p.relative_to(root)))
    return hosts, words


def _locate(dist, f) -> Path | None:
    try:
        return Path(dist.locate_file(f))
    except Exception:  # a file the metadata names oddly: nothing to scan
        return None


def production() -> set[str]:
    """The packages the image carries: what the lock reaches from the project without its
    dev groups (uv.lock's own graph, markers ignored)."""
    import tomllib

    lock = tomllib.loads(LOCK.read_text())
    by_name = {p["name"]: p for p in lock["package"]}
    root = by_name.get("moolakata") or {}
    todo = [d["name"] for d in root.get("dependencies", [])]
    out: set[str] = set()
    while todo:
        name = todo.pop()
        if name in out or name not in by_name:
            continue
        out.add(name)
        todo += [d["name"] for d in by_name[name].get("dependencies", [])]
        for extra in by_name[name].get("optional-dependencies", {}).values():
            todo += [d["name"] for d in extra]
    return out


def scan() -> dict:
    """What each installed package and vendored library could reach, by host, and the files
    naming telemetry or update checks."""
    out: dict[str, dict] = {}
    shipped = production()
    for dist in metadata.distributions():
        name = (dist.metadata["Name"] or "").lower()
        if not name or dist.files is None:
            continue
        roots = set()
        for f in dist.files:
            full = _locate(dist, f)
            if (
                full is not None
                and full.suffix in (".py", ".so", ".pyd", ".json", ".txt")
                and not SKIP.search(str(full))
            ):
                roots.add(full)
        hosts, words = set(), []
        for p in sorted(roots):
            h, w = _scan_file(p)
            hosts |= h
            if w:
                words.append(p.name)
        if hosts or words:
            out[name] = {
                "hosts": sorted(hosts),
                "words": sorted(set(words))[:20],
                "inImage": name in shipped,
            }
    manifest = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {"packages": {}}
    for name, pkg in manifest.get("packages", {}).items():
        folder = MANIFEST.parent / pkg.get("dir", name)
        if folder.is_dir():
            hosts, words = _scan_tree(folder)
            if hosts or words:
                out[f"npm:{name}"] = {
                    "hosts": sorted(hosts),
                    "words": sorted(set(words))[:20],
                    "inImage": True,
                }
    return dict(sorted(out.items()))


def record() -> dict:
    try:
        return json.loads(AUDIT.read_text())
    except OSError, ValueError:
        return {}


def hashes() -> dict[str, str]:
    return {"uv.lock": _hash(LOCK), "manifest.json": _hash(MANIFEST)}


def diff(found: dict, accepted: dict) -> list[str]:
    lines = []
    for name, f in found.items():
        was = accepted.get(name) or {"hosts": [], "words": []}
        new_hosts = sorted(set(f["hosts"]) - set(was["hosts"]))
        new_words = sorted(set(f["words"]) - set(was["words"]))
        if new_hosts or new_words:
            tag = "" if f.get("inImage", True) else " (dev only)"
            lines.append(
                f"{name}{tag}: " + ", ".join(new_hosts + [f"words in {w}" for w in new_words])
            )
    for name in sorted(set(accepted) - set(found)):
        lines.append(f"{name}: gone")
    return lines


def cmd_scan() -> int:
    found = scan()
    rec = record()
    lines = diff(found, rec.get("findings", {}))
    if lines:
        print("New since the register last accepted (docs/dependencies.md; then `accept`):")
        print("\n".join("  " + x for x in lines))
    else:
        print("Nothing new since the register last accepted.")
    shipped = [n for n, f in found.items() if f.get("inImage")]
    print(
        f"\n{len(shipped)} packages in the image name a host or a telemetry word "
        f"({len(found) - len(shipped)} more are dev only); the image's in full:"
    )
    for name in shipped:
        f = found[name]
        print(
            f"  {name}: {', '.join(f['hosts'])}"
            + (f"  [words: {', '.join(f['words'])}]" if f["words"] else "")
        )
    return 1 if lines else 0


def cmd_accept() -> int:
    import datetime as dt

    rec = record()
    rec.update(
        {
            "auditedAt": dt.date.today().isoformat(),
            "hashes": hashes(),
            "findings": scan(),
        }
    )
    AUDIT.write_text(json.dumps(rec, indent=2, sort_keys=True) + "\n")
    print(f"recorded in {AUDIT.relative_to(paths.ROOT)}")
    return 0


def cmd_check() -> int:
    rec = record()
    have = hashes()
    stale = [k for k, v in have.items() if rec.get("hashes", {}).get(k) != v]
    if stale:
        print(
            f"{', '.join(stale)} changed since the dependency register was audited: run "
            "`web/dev.sh audit`, review docs/dependencies.md, then `web/dev.sh audit --accept`",
            file=sys.stderr,
        )
        return 1
    return 0


def main(argv: list[str]) -> int:
    what = argv[1] if len(argv) > 1 else "scan"
    return {"scan": cmd_scan, "accept": cmd_accept, "check": cmd_check}.get(what, cmd_scan)()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
