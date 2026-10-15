"""Time zones (requirements S14.9): timestamps are stored in UTC and shown in the viewer's
zone; the server's own zone is read from the host."""

import os
from functools import cache
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones


@cache
def host_zone() -> str:
    """The host's zone: TZ, then /etc/timezone, then where /etc/localtime points; else UTC."""
    candidates = [os.environ.get("TZ", "").lstrip(":")]
    tz_file = Path("/etc/timezone")
    if tz_file.is_file():
        candidates.append(tz_file.read_text().strip())
    localtime = Path("/etc/localtime")
    if localtime.is_symlink():
        target = str(localtime.resolve())
        if "zoneinfo/" in target:
            candidates.append(target.split("zoneinfo/", 1)[1])
    for name in candidates:
        if name and valid(name):
            return name
    return "UTC"


def valid(name: str) -> bool:
    try:
        ZoneInfo(name)
    except ZoneInfoNotFoundError, ValueError:
        return False
    return True


@cache
def names() -> list[str]:
    return sorted(z for z in available_timezones() if "/" in z and not z.startswith("Etc/"))


def zone_for(choice: str | None) -> str:
    """A user's zone: "auto" (or none) is the server's (S14.9.2)."""
    return host_zone() if not choice or choice == "auto" else choice
