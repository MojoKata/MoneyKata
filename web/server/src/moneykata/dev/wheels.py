"""Every locked dependency must install from a published wheel on amd64 and arm64 (requirements
§20.8.1), since compiling under emulation is too slow.

    python -m moneykata.dev.wheels [uv.lock]
"""

import re
import sys
import tomllib
from pathlib import Path

LOCK = Path(__file__).resolve().parents[3] / "uv.lock"
ARCHES = {"amd64": ("x86_64",), "arm64": ("aarch64",)}


def fits(filename: str, machine: str) -> bool:
    """A wheel that installs on glibc Linux for CPython 3.12 on this machine."""
    python, abi, platform = filename[:-4].split("-")[-3:]

    def python_ok(tag: str) -> bool:
        if tag in ("py3", "cp312"):
            return True
        stable = re.fullmatch(r"cp3(\d+)", tag)
        return bool(stable) and int(stable.group(1)) <= 12 and abi == "abi3"

    if not any(python_ok(t) for t in python.split(".")):
        return False
    if not any(a in ("none", "abi3", "cp312") for a in abi.split(".")):
        return False
    return any(
        p == "any" or (p.startswith(("manylinux", "linux")) and p.endswith(machine))
        for p in platform.split(".")
    )


def missing(lock_path: Path = LOCK) -> list[str]:
    lock = tomllib.loads(lock_path.read_text())
    problems = []
    for pkg in lock["package"]:
        if pkg.get("source", {}).get("editable") or pkg.get("source", {}).get("virtual"):
            continue
        wheels = [w["url"].rsplit("/", 1)[-1] for w in pkg.get("wheels", [])]
        for arch, machines in ARCHES.items():
            if not any(fits(w, m) for w in wheels for m in machines):
                problems.append(f"{pkg['name']} {pkg['version']}: no wheel for {arch}")
    return problems


def main(argv: list[str]) -> int:
    problems = missing(Path(argv[1]) if len(argv) > 1 else LOCK)
    for p in problems:
        print(p, file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
