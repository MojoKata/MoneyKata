"""The server's idea of now. Code asks here instead of the datetime module, so the generated
mockup (requirements §15.9) can be built on a fixed day and come out the same every time."""

import datetime as dt

_fixed: dt.datetime | None = None


def now() -> dt.datetime:
    return _fixed if _fixed is not None else dt.datetime.now(dt.UTC)


def today() -> dt.date:
    """Today in UTC; a user's today follows their zone (§17.9.5) where it matters."""
    return now().date()


def fix(at: dt.datetime | None) -> None:
    """Freeze the clock (the mockup's build), or release it with None."""
    global _fixed
    _fixed = at
