"""The holidays people get gifts for (requirements S7.7.2), with their dates computed per year:
fixed dates, rule-based ones, and lunar or lunisolar ones from shipped tables."""

import calendar
import datetime as dt


def _nth(year: int, month: int, weekday: int, n: int) -> dt.date:
    """The nth weekday (Monday 0) of a month; n = -1 for the last."""
    days = [
        d
        for d in calendar.Calendar().itermonthdates(year, month)
        if d.month == month and d.weekday() == weekday
    ]
    return days[n - 1] if n > 0 else days[n]


# Lunar and lunisolar holidays: their first day each year (in the US), as published calendars
# give them. A year past the table has no date until the table is updated with the tax tables.
TABLES = {
    "hanukkah": {
        2024: (12, 26),
        2025: (12, 15),
        2026: (12, 5),
        2027: (12, 25),
        2028: (12, 13),
        2029: (12, 2),
        2030: (12, 21),
    },
    "diwali": {
        2024: (11, 1),
        2025: (10, 20),
        2026: (11, 8),
        2027: (10, 29),
        2028: (10, 17),
        2029: (11, 5),
        2030: (10, 26),
    },
    "lunar-new-year": {
        2024: (2, 10),
        2025: (1, 29),
        2026: (2, 17),
        2027: (2, 6),
        2028: (1, 26),
        2029: (2, 13),
        2030: (2, 3),
    },
    "eid-al-fitr": {
        2024: (4, 10),
        2025: (3, 30),
        2026: (3, 20),
        2027: (3, 10),
        2028: (2, 27),
        2029: (2, 15),
        2030: (2, 5),
    },
}

# key: (label, how its date is found)
HOLIDAYS: dict[str, tuple[str, object]] = {
    "christmas": ("Christmas", (12, 25)),
    "valentines": ("Valentine's Day", (2, 14)),
    "mothers-day": ("Mother's Day", lambda y: _nth(y, 5, 6, 2)),
    "fathers-day": ("Father's Day", lambda y: _nth(y, 6, 6, 3)),
    "thanksgiving": ("Thanksgiving", lambda y: _nth(y, 11, 3, 4)),
    "hanukkah": ("Hanukkah", "table"),
    "diwali": ("Diwali", "table"),
    "lunar-new-year": ("Lunar New Year", "table"),
    "eid-al-fitr": ("Eid al-Fitr", "table"),
}


def label(key: str) -> str:
    return HOLIDAYS[key][0]


def date_of(key: str, year: int) -> dt.date | None:
    """The holiday's date in a year, or None when the shipped table doesn't reach it."""
    rule = HOLIDAYS[key][1]
    if isinstance(rule, tuple):
        return dt.date(year, *rule)
    if callable(rule):
        return rule(year)
    found = TABLES[key].get(year)
    return dt.date(year, *found) if found else None
