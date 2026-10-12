#!/usr/bin/env python3
"""Vendored browser libraries: verify the committed npm tarballs and unpack what the app loads.

    vendor.py extract   check each tarball's hash, then unpack the files manifest.json lists
    vendor.py verify    check the hashes only
    vendor.py add NAME VERSION   download a tarball from the npm registry and print its entry

Each package's tarball is committed beside this file, named and hashed in manifest.json. Its
files unpack to vendor/<dir>/<path inside the package>, where the import map in index.html
points. The unpacked files are not committed.
"""

import base64
import hashlib
import json
import shutil
import sys
import tarfile
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "manifest.json"


def load() -> dict:
    return json.loads(MANIFEST.read_text())


def sri(data: bytes) -> str:
    return "sha512-" + base64.b64encode(hashlib.sha512(data).digest()).decode()


def verify(manifest: dict) -> list[str]:
    problems = []
    for name, pkg in manifest["packages"].items():
        path = HERE / pkg["tarball"]
        if not path.is_file():
            problems.append(f"{name}: {pkg['tarball']} is missing")
        elif sri(path.read_bytes()) != pkg["integrity"]:
            problems.append(f"{name}: {pkg['tarball']} does not match its integrity hash")
    return problems


def extract(manifest: dict) -> None:
    for pkg in manifest["packages"].values():
        target = HERE / pkg["dir"]
        if target.exists():
            shutil.rmtree(target)
        with tarfile.open(HERE / pkg["tarball"], "r:gz") as tar:
            for rel in pkg["files"]:
                member = tar.getmember("package/" + rel)
                if not member.isfile():
                    raise SystemExit(f"{pkg['tarball']}: {rel} is not a regular file")
                source = tar.extractfile(member)
                assert source is not None
                out = target / rel
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(source.read())


def add(name: str, version: str) -> None:
    meta_url = f"https://registry.npmjs.org/{name}/{version}"
    with urllib.request.urlopen(meta_url, timeout=60) as r:  # noqa: S310 - fixed https host
        meta = json.load(r)
    url = meta["dist"]["tarball"]
    with urllib.request.urlopen(url, timeout=300) as r:  # noqa: S310 - from the registry
        data = r.read()
    if sri(data) != meta["dist"]["integrity"]:
        raise SystemExit(f"{name}@{version}: download does not match the registry's integrity")
    filename = name.lstrip("@").replace("/", "-") + f"-{version}.tgz"
    (HERE / filename).write_bytes(data)
    entry = {"version": version, "tarball": filename, "integrity": meta["dist"]["integrity"]}
    print(json.dumps({name: entry}, indent=2))


def main(argv: list[str]) -> int:
    command = argv[1] if len(argv) > 1 else ""
    if command == "add" and len(argv) == 4:
        add(argv[2], argv[3])
        return 0
    if command not in ("extract", "verify"):
        print(__doc__.strip())
        return 2
    manifest = load()
    problems = verify(manifest)
    for p in problems:
        print(p, file=sys.stderr)
    if problems:
        return 1
    if command == "extract":
        extract(manifest)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
