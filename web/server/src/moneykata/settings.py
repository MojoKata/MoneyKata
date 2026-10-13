"""Settings (requirements S16): what admins change at run time, stored in the database. Each
setting is declared once here with its section, default and check; values are JSON. There is
no cache: a change applies to the very next read (R3.7)."""

import datetime as dt
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.orm import Session

from .errors import FieldError, Problem
from .store.entities.core import Setting


class Invalid(ValueError):
    pass


def _int(lo: int, hi: int) -> Callable[[Any], int]:
    def check(v: Any) -> int:
        if isinstance(v, bool) or not isinstance(v, int):
            raise Invalid("a whole number")
        if not lo <= v <= hi:
            raise Invalid(f"between {lo} and {hi}")
        return v

    return check


def _bool(v: Any) -> bool:
    if not isinstance(v, bool):
        raise Invalid("on or off")
    return v


def _text(max_len: int, allow_empty: bool = False) -> Callable[[Any], str]:
    def check(v: Any) -> str:
        if not isinstance(v, str):
            raise Invalid("text")
        v = v.strip()
        if not v and not allow_empty:
            raise Invalid("cannot be empty")
        if len(v) > max_len:
            raise Invalid(f"at most {max_len} characters")
        return v

    return check


def _time(v: Any) -> str:
    if not isinstance(v, str) or not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", v):
        raise Invalid("a time of day as HH:MM")
    return v


def _zone(v: Any) -> str:
    try:
        ZoneInfo(v)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        raise Invalid("a time zone name, such as America/New_York") from None
    return v


def _url(v: Any) -> str | None:
    if v in (None, ""):
        return None
    if not isinstance(v, str) or not re.fullmatch(r"https?://[^\s/]+(/[^\s]*)?", v):
        raise Invalid("an address such as https://money.example.lan")
    return v.rstrip("/")


def _domains(v: Any) -> list[str]:
    if not isinstance(v, list) or not all(isinstance(d, str) for d in v):
        raise Invalid("a list of email domains")
    out = []
    for d in v:
        d = d.strip().lower().lstrip("@")
        if not re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,}", d):
            raise Invalid(f"{d!r} is not an email domain")
        out.append(d)
    return out


def _host(v: Any) -> str | None:
    if v in (None, ""):
        return None
    if not isinstance(v, str) or not re.fullmatch(r"[A-Za-z0-9.:\[\]-]{1,253}", v.strip()):
        raise Invalid("a host name or address, such as smtp.example.com")
    return v.strip().lower()


def _choice(*options: str) -> Callable[[Any], str]:
    def check(v: Any) -> str:
        if v not in options:
            raise Invalid("one of " + ", ".join(options))
        return v

    return check


def _optional_text(max_len: int) -> Callable[[Any], str | None]:
    def check(v: Any) -> str | None:
        if v in (None, ""):
            return None
        return _text(max_len)(v)

    return check


def _address(v: Any) -> str | None:
    """An email address, with a name if wanted: `MoneyKata <money@example.com>`."""
    if v in (None, ""):
        return None
    if not isinstance(v, str) or not re.fullmatch(
        r"([^<>@\n]+<[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+>|[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+)", v.strip()
    ):
        raise Invalid("an email address, such as MoneyKata <money@example.com>")
    return v.strip()


def _avatar(v: Any) -> dict:
    """The household's avatar: initials with a colour, or an uploaded image's id."""
    if not isinstance(v, dict) or v.get("kind") not in ("initials", "image"):
        raise Invalid("initials or an image")
    if v["kind"] == "initials":
        initials = str(v.get("initials", "")).strip()
        if not 1 <= len(initials) <= 3:
            raise Invalid("one to three letters")
        color = str(v.get("color", "#3b7a57"))
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
            raise Invalid("a colour such as #3b7a57")
        return {"kind": "initials", "initials": initials, "color": color}
    image = v.get("image")
    if not isinstance(image, str) or not image.startswith("data:image/"):
        raise Invalid("an image")
    return {"kind": "image", "image": image}


@dataclass(frozen=True)
class Definition:
    key: str
    section: str
    default: Any
    check: Callable[[Any], Any]


DEFINITIONS: dict[str, Definition] = {}


def _d(key: str, section: str, default: Any, check: Callable[[Any], Any]) -> None:
    DEFINITIONS[key] = Definition(key, section, default, check)


# General (S16.1)
_d("serverName", "general", "moneykata", _text(60))
_d("householdName", "general", "Our household", _text(60))
_d(
    "householdAvatar",
    "general",
    {"kind": "initials", "initials": "MK", "color": "#3b7a57"},
    _avatar,
)
_d("publicUrl", "general", None, _url)
# Email (S16.2): until a host is set, emails are written to the mail folder
_d("smtpHost", "email", None, _host)
_d("smtpPort", "email", 587, _int(1, 65535))
_d("smtpSecurity", "email", "starttls", _choice("starttls", "tls", "none"))
_d("smtpUsername", "email", None, _optional_text(200))
_d("smtpFrom", "email", None, _address)
# Sign-in and sessions (S16.3, S13.7.1)
_d("sessionIdleHours", "sessions", 8, _int(1, 24 * 7))
_d("sessionAbsoluteDays", "sessions", 30, _int(1, 365))
_d("lockoutFailures", "sessions", 10, _int(3, 100))
_d("lockoutMinutes", "sessions", 15, _int(1, 24 * 60))
# Sign-up (S16.4)
_d("signupEnabled", "signup", False, _bool)
_d("signupDomains", "signup", [], _domains)
# Passwords (S16.5)
_d("passwordMinLength", "passwords", 12, _int(8, 128))
# Prices (S16.6): the sources themselves are records of their own
_d("priceRefreshTime", "prices", "18:00", _time)
_d("priceRefreshZone", "prices", "America/New_York", _zone)
# Imports (S16.8)
_d("importMaxMb", "imports", 25, _int(1, 200))
# Backups (S16.12, S14.6)
_d("backupTime", "backups", "02:30", _time)
_d("backupCopies", "backups", 14, _int(1, 365))
# Alerts (S16.16, S12.11): how long a source may fail first, and the daily summary's time
_d("alertSourceHours", "alerts", 48, _int(1, 24 * 14))
_d("alertSummaryTime", "alerts", "07:00", _time)
# Key storage (S15.8.2): remind admins of the key's age; 0 is off
_d("keyReminderMonths", "keys", 12, _int(0, 120))


def coerce(key: str, value: Any) -> Any:
    d = DEFINITIONS.get(key)
    if d is None:
        raise Problem(
            422,
            "unknown-setting",
            f"There is no setting {key!r}.",
            [FieldError(key, "unknown-setting", "no such setting")],
        )
    try:
        return d.check(value)
    except Invalid as e:
        raise Problem(
            422,
            "invalid-setting",
            f"{key}: {e}",
            [FieldError(key, "invalid-setting", f"Must be {e}.")],
        ) from None


def get(s: Session, key: str) -> Any:
    row = s.get(Setting, key)
    if row is None or row.deleted:
        return DEFINITIONS[key].default
    return json.loads(row.value)


def section(s: Session, name: str) -> dict[str, Any]:
    keys = [k for k, d in DEFINITIONS.items() if d.section == name]
    rows = {r.key: r for r in s.scalars(select(Setting).where(Setting.key.in_(keys)))}
    return {
        k: json.loads(rows[k].value)
        if k in rows and not rows[k].deleted
        else DEFINITIONS[k].default
        for k in keys
    }


def put(s: Session, key: str, value: Any, by: str | None) -> Any:
    value = coerce(key, value)
    row = s.get(Setting, key)
    text = json.dumps(value, sort_keys=True)
    if row is None:
        s.add(Setting(key=key, value=text, updatedById=by))
    else:
        row.value = text
        row.updatedById = by
    return value


def time_of(s: Session, key: str) -> dt.time:
    hh, mm = get(s, key).split(":")
    return dt.time(int(hh), int(mm))
