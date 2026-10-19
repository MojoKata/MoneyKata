"""The base image's digest (requirements S17.8.5): both Dockerfiles pin
`python:3.14-slim-bookworm` by digest, which moves with each release and on a Debian or
Python fix. `update` fetches the tag's current digest from Docker Hub, writes it into both
Dockerfiles and records the move in web/audit.json; `check` warns, without failing, when the
recorded move is older than 90 days.

    python -m moolakata.dev.base update [--packages]   --packages: diff the Debian packages
    python -m moolakata.dev.base check
"""

import datetime as dt
import json
import re
import shutil
import subprocess
import sys
import urllib.request

from .. import paths
from .audit import AUDIT, record

DOCKERFILES = (paths.WEB / "install" / "Dockerfile", paths.ROOT / "connector" / "Dockerfile")
ARG = re.compile(r"^ARG PYTHON=(?P<image>[\w.-]+:[\w.-]+)@(?P<digest>sha256:[0-9a-f]{64})$", re.M)
WARN_DAYS = 90


def pinned() -> tuple[str, str]:
    m = ARG.search(DOCKERFILES[0].read_text())
    if not m:
        raise SystemExit("no pinned base image in web/install/Dockerfile")
    return m["image"], m["digest"]


def current_digest(image: str) -> str:
    name, tag = image.split(":", 1)
    url = f"https://hub.docker.com/v2/repositories/library/{name}/tags/{tag}"
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.load(r)["digest"]


def packages(ref: str) -> dict[str, str]:
    docker = shutil.which("docker") or "docker"
    args = [docker, "run", "--rm", "--entrypoint", "dpkg-query", ref, "-W", "-f"]
    args.append("${Package} ${Version}\\n")
    out = subprocess.run(args, capture_output=True, text=True, check=True).stdout  # noqa: S603
    return dict(line.split(" ", 1) for line in out.splitlines() if " " in line)


def cmd_update(diff_packages: bool) -> int:
    image, old = pinned()
    new = current_digest(image)
    if new == old:
        print(f"{image} is at the current digest already ({old[:19]}…)")
    else:
        for path in DOCKERFILES:
            text = path.read_text()
            path.write_text(ARG.sub(f"ARG PYTHON={image}@{new}", text))
        print(f"{image}: {old[:19]}… → {new[:19]}… in {len(DOCKERFILES)} Dockerfiles")
        if diff_packages:
            before, after = packages(f"{image}@{old}"), packages(f"{image}@{new}")
            for name in sorted(set(before) | set(after)):
                if before.get(name) != after.get(name):
                    print(f"  {name}: {before.get(name, '—')} → {after.get(name, '—')}")
    rec = record()
    rec["base"] = {"image": image, "digest": new, "movedAt": dt.date.today().isoformat()}
    AUDIT.write_text(json.dumps(rec, indent=2, sort_keys=True) + "\n")
    return 0


def cmd_check() -> int:
    image, digest = pinned()
    base = record().get("base") or {}
    moved = base.get("movedAt")
    if base.get("digest") != digest or not moved:
        print(
            f"warning: {image}'s digest isn't recorded in web/audit.json: "
            "run `web/dev.sh base-update`"
        )
        return 0
    age = (dt.date.today() - dt.date.fromisoformat(moved)).days
    if age > WARN_DAYS:
        print(
            f"warning: {image}'s digest was last moved {age} days ago: run `web/dev.sh base-update`"
        )
    else:
        print(f"{image}: digest moved {age} days ago")
    return 0


def main(argv: list[str]) -> int:
    what = argv[1] if len(argv) > 1 else "check"
    if what == "update":
        return cmd_update("--packages" in argv)
    return cmd_check()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
