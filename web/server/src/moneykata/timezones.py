"""Time zones (requirements S14.9): timestamps are stored in UTC and shown in the viewer's
zone; the server's own zone is read from the host."""

import datetime as dt
import io
import os
import time
from datetime import tzinfo
from functools import cache
from pathlib import Path
from zoneinfo import TZPATH, ZoneInfo, ZoneInfoNotFoundError, available_timezones


@cache
def host_zone() -> str:
    return zone_from(os.environ, Path("/etc/timezone"), Path("/etc/localtime"))


def zone_from(env, timezone_file: Path, localtime: Path) -> str:
    """The host's zone (S14.9.2): TZ; else the zone /etc/localtime keeps the time of, by the
    name its link or /etc/timezone gives when that zone keeps the same time, else by the zone's
    own name; else those names; else UTC. What the file holds comes first because in a
    container both names are the image's (Etc/UTC): the host's file, mounted at /etc/localtime,
    lands on the link's target, so the data is the host's and the names aren't."""
    given = env.get("TZ", "").lstrip(":")
    if given and valid(given):
        return given
    written = timezone_file.read_text().strip() if timezone_file.is_file() else ""
    named = ""
    if localtime.is_symlink():
        target = str(localtime.resolve())
        if "zoneinfo/" in target:
            named = target.split("zoneinfo/", 1)[1]
    try:
        data = localtime.read_bytes()
    except OSError:
        data = b""
    if data and (offsets := _offsets_of(data)) is not None:
        for name in (named, written):
            if name and valid(name) and _offsets(_zone(name), _STAMPS) == offsets:
                return name
        if held := zones_of(data):
            return canonical(held)
    for name in (written, named):
        if name and valid(name):
            return name
    return "UTC"


def zone_of(data: bytes) -> str:
    """The name of the zone a compiled zone file keeps the time of, or "" when none does."""
    return canonical(zones_of(data))


def zones_of(data: bytes) -> list[str]:
    """Every zone that keeps the same time as a compiled zone file: the same UTC offset at
    every week since 1970. Compared by what they do, not their bytes, since two systems'
    tzdata compile the same zone differently. A few recent weeks narrow the field first; of
    zones alike in that, those with the same abbreviations too (London's BST, not Dublin's
    IST), when any have."""
    host = _from(data)
    if host is None:
        return []
    offsets = _offsets(host, _STAMPS)
    recent = offsets[-len(_RECENT) :]
    found = [n for n in names() if _offsets(_zone(n), _RECENT) == recent]
    found = [n for n in found if _offsets(_zone(n), _STAMPS) == offsets]
    abbreviated = _abbreviations(host)
    return [n for n in found if _abbreviations(_zone(n)) == abbreviated] or found


def canonical(found: list[str]) -> str:
    """Of names for the same zone, the one tzdata lists as the zone's own (zone1970.tab), so
    a host in Los Angeles is America/Los_Angeles rather than US/Pacific."""
    listed = _listed()
    return next((n for n in found if n in listed), found[0] if found else "")


# UTC is known as such: in a container its file is the one the host's zone is mounted over.
_UTC = {"UTC", "Etc/UTC", "Etc/UCT", "Etc/Universal", "Etc/Zulu", "UCT", "Universal", "Zulu"}
_WEEK = 7 * 86400
_STAMPS = tuple(range(0, int(time.time()) + 2 * 365 * 86400, _WEEK))  # 1970 to two years on
_RECENT = _STAMPS[-160:]


def _zone(name: str) -> tzinfo:
    return dt.UTC if name in _UTC else ZoneInfo(name)


def _offsets(zone: tzinfo, stamps) -> list:
    return [dt.datetime.fromtimestamp(s, zone).utcoffset() for s in stamps]


def _abbreviations(zone: tzinfo) -> list:
    return [dt.datetime.fromtimestamp(s, zone).tzname() for s in _RECENT]


def _from(data: bytes) -> tzinfo | None:
    try:
        return ZoneInfo.from_file(io.BytesIO(data))
    except ValueError, OSError:
        return None


def _offsets_of(data: bytes) -> list | None:
    zone = _from(data)
    return None if zone is None else _offsets(zone, _STAMPS)


@cache
def _listed() -> frozenset[str]:
    for root in map(Path, TZPATH):
        try:
            text = (root / "zone1970.tab").read_text()
        except OSError:
            continue
        return frozenset(
            line.split("\t")[2] for line in text.splitlines() if line and not line.startswith("#")
        )
    return frozenset()


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
