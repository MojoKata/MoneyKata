#!/usr/bin/env python3
"""Vendored browser libraries: verify the committed npm tarballs and unpack what the app loads.

    vendor.py extract   check each tarball's hash, then unpack the files manifest.json lists
    vendor.py verify    check the hashes only
    vendor.py add NAME VERSION [--young REASON] [--dir DIR] [--file PATH ...]
                        adopt a version from the npm registry (run it as `web/dev.sh vendor add`,
                        which has sigstore): refuse one published less than 14 days ago unless
                        --young gives the reason, check the download against the registry's
                        integrity hash, verify its provenance, write its manifest entry and the
                        diff of the served files for review

Each package's tarball is committed beside this file, named and hashed in manifest.json. Its
files unpack to vendor/<dir>/<path inside the package>, where the import map in index.html
points. The unpacked files are not committed.

The hash records exactly what was adopted and catches a tarball changed in the working tree; it
does not judge a release. That is the job of `add` (requirements S13.7.11, S17.3.1).
"""

import argparse
import base64
import difflib
import hashlib
import io
import json
import shutil
import sys
import tarfile
import tempfile
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "manifest.json"
REGISTRY = "https://registry.npmjs.org"
COOLDOWN = timedelta(days=14)
GITHUB_ACTIONS = "https://token.actions.githubusercontent.com"
SLSA_PROVENANCE = "https://slsa.dev/provenance/v1"


def load() -> dict:
    return json.loads(MANIFEST.read_text())


def save(manifest: dict) -> None:
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")


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


def read_files(tarball: bytes, files: list[str]) -> dict[str, bytes]:
    """The listed files of a package tarball; a missing one or one that isn't a file refuses."""
    out = {}
    with tarfile.open(fileobj=io.BytesIO(tarball), mode="r:gz") as tar:
        for rel in files:
            try:
                member = tar.getmember("package/" + rel)
            except KeyError:
                raise SystemExit(f"{rel} is not in the package") from None
            if not member.isfile():
                raise SystemExit(f"{rel} is not a regular file")
            source = tar.extractfile(member)
            assert source is not None
            out[rel] = source.read()
    return out


def extract(manifest: dict) -> None:
    for pkg in manifest["packages"].values():
        target = HERE / pkg["dir"]
        if target.exists():
            shutil.rmtree(target)
        data = (HERE / pkg["tarball"]).read_bytes()
        try:
            files = read_files(data, pkg["files"])
        except SystemExit as e:
            raise SystemExit(f"{pkg['tarball']}: {e}") from None
        for rel, content in files.items():
            out = target / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(content)


# Adopting a version


def fetch(url: str, timeout: int = 300) -> bytes:
    with urllib.request.urlopen(url, timeout=timeout) as r:  # noqa: S310 - fixed https host
        return r.read()


def repository_url(meta: dict) -> str:
    """The package's source repository as an https URL, as the provenance certificate names it."""
    repo = meta.get("repository") or {}
    url = repo if isinstance(repo, str) else repo.get("url", "")
    url = url.removeprefix("git+").removesuffix(".git")
    if url.startswith("git://"):
        url = "https://" + url[len("git://") :]
    return url


def cooldown(published: datetime, now: datetime, young: str | None) -> None:
    """Refuse a release younger than the cooldown unless a reason is given."""
    age = now - published
    if age >= COOLDOWN:
        return
    if young:
        print(f"published {age.days} days ago; cooldown waived: {young}")
        return
    ready = (published + COOLDOWN).date().isoformat()
    raise SystemExit(
        f"published {age.days} days ago, under the {COOLDOWN.days}-day cooldown; "
        f"adopt it from {ready}, or give --young REASON (a security fix, say)"
    )


def provenance(name: str, version: str, data: bytes, attestations_url: str, repository: str):
    """Verify the SLSA provenance npm holds for this tarball: signed through Sigstore by a GitHub
    Actions run of `repository`, for this package, version and hash. Returns the build's
    workflow. Uses the trust root sigstore ships with (pinned in uv.lock), so it works without
    reaching Sigstore's update service."""
    import logging

    from sigstore.models import Bundle
    from sigstore.verify import Verifier, policy

    logging.getLogger("sigstore").setLevel(logging.ERROR)  # quiet about the offline trust root

    doc = json.loads(fetch(attestations_url, timeout=60))
    bundles = [a["bundle"] for a in doc["attestations"] if a["predicateType"] == SLSA_PROVENANCE]
    if not bundles:
        raise SystemExit(f"{name}@{version}: the registry lists no SLSA provenance")
    identity = policy.AllOf(
        [policy.OIDCIssuerV2(GITHUB_ACTIONS), policy.OIDCSourceRepositoryURI(repository)]
    )
    try:
        _, payload = Verifier.production(offline=True).verify_dsse(
            Bundle.from_json(json.dumps(bundles[0])), identity
        )
    except Exception as e:
        raise SystemExit(f"{name}@{version}: provenance does not verify: {e}") from None
    statement = json.loads(payload)
    purl = f"pkg:npm/{name.replace('@', '%40')}@{version}"  # a package URL escapes the scope's @
    sha512 = hashlib.sha512(data).hexdigest()
    if not any(
        s.get("name") == purl and s.get("digest", {}).get("sha512") == sha512
        for s in statement.get("subject", [])
    ):
        raise SystemExit(f"{name}@{version}: provenance is for a different package or tarball")
    build = statement["predicate"]["buildDefinition"]["externalParameters"]["workflow"]
    return f"{build['repository']} {build['path']} at {build['ref']}"


def diff(old: dict[str, bytes], new: dict[str, bytes], label: tuple[str, str]) -> str:
    """A unified diff of the served files, old version to new."""
    lines = []
    for rel in sorted(old.keys() | new.keys()):
        a = old.get(rel, b"").decode("utf-8", "replace").splitlines(keepends=True)
        b = new.get(rel, b"").decode("utf-8", "replace").splitlines(keepends=True)
        lines += difflib.unified_diff(a, b, f"{label[0]}/{rel}", f"{label[1]}/{rel}")
    return "".join(lines)


def add(
    name: str, version: str, young: str | None, dir_: str | None, files: list[str] | None
) -> None:
    manifest = load()
    current = manifest["packages"].get(name)
    meta = json.loads(fetch(f"{REGISTRY}/{urllib.parse.quote(name, safe='@')}"))
    if version not in meta.get("versions", {}):
        raise SystemExit(f"{name}@{version} is not in the registry")
    release = meta["versions"][version]

    # 1. Cooldown: most malicious releases are found and pulled within days.
    published = datetime.fromisoformat(meta["time"][version].replace("Z", "+00:00"))
    cooldown(published, datetime.now(UTC), young)

    # 2. The download is the tarball the registry lists.
    data = fetch(release["dist"]["tarball"])
    if sri(data) != release["dist"]["integrity"]:
        raise SystemExit(f"{name}@{version}: download does not match the registry's integrity")

    # 3. Provenance, from the repository already recorded for the package.
    repository = (current or {}).get("repository") or repository_url(release)
    attestations = release["dist"].get("attestations", {}).get("url")
    if attestations:
        build = provenance(name, version, data, attestations, repository)
        print(f"provenance verified: built by {build}")
    elif current and current.get("provenance"):
        raise SystemExit(
            f"{name}@{version} has no provenance, though {current['version']} had: "
            "it may have been published outside the project's own build"
        )
    else:
        print(f"{name}@{version} publishes no provenance: review the diff with that in mind")

    if release.get("dependencies"):
        print(
            f"depends on {', '.join(release['dependencies'])}: vendor each too, unless the "
            "served files bundle them"
        )

    # 4. The manifest entry, keeping the package's place and served files.
    dir_ = dir_ or (current or {}).get("dir") or name.rsplit("/", 1)[-1]
    files = files or (current or {}).get("files") or []
    served = read_files(data, files)
    tarball = name.lstrip("@").replace("/", "-") + f"-{version}.tgz"
    (HERE / tarball).write_bytes(data)
    entry = {
        "version": version,
        "published": published.date().isoformat(),
        "tarball": tarball,
        "integrity": release["dist"]["integrity"],
        "repository": repository,
        "provenance": bool(attestations),
        "dir": dir_,
        "files": files,
    }
    if young and published > datetime.now(UTC) - COOLDOWN:
        entry["cooldownWaived"] = young
    manifest["packages"][name] = entry
    save(manifest)

    # 5. What changes in the files the browser loads, for review before committing.
    if current and current["tarball"] != tarball:
        old_path = HERE / current["tarball"]
        old = read_files(old_path.read_bytes(), current["files"])
        text = diff(old, served, (current["version"], version))
        out = (
            Path(tempfile.mkdtemp(prefix="vendor-")) / f"{dir_}-{current['version']}-{version}.diff"
        )
        out.write_text(text)
        changed = sum(1 for rel in served if old.get(rel) != served[rel])
        print(f"{changed} of {len(served)} served files changed; review the diff: {out}")
        old_path.unlink()
    if not files:
        print(f'list the files the import map needs under {name}\'s "files", then extract')
    print(f"{name}@{version} written to manifest.json; run `vendor.py extract` and commit both")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="vendor.py", description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("extract")
    sub.add_parser("verify")
    a = sub.add_parser("add")
    a.add_argument("name")
    a.add_argument("version")
    a.add_argument("--young", metavar="REASON", help="adopt a release inside the cooldown")
    a.add_argument("--dir", help="where a new package unpacks (default: its name)")
    a.add_argument("--file", action="append", help="a file a new package serves (repeat)")
    args = parser.parse_args(argv[1:])
    if args.command == "add":
        add(args.name, args.version, args.young, args.dir, args.file)
        return 0
    manifest = load()
    problems = verify(manifest)
    for p in problems:
        print(p, file=sys.stderr)
    if problems:
        return 1
    if args.command == "extract":
        extract(manifest)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
