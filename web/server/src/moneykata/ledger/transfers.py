"""Transfers between two of a user's accounts (requirements S1.7): the same amount, the other
way, a few days apart. Matched transfers count neither as spending nor as income."""

import datetime as dt

DAYS = 4


def candidates(t, others: list) -> list:
    """Unmatched transactions in other accounts that could be the other half of t."""
    return [
        o
        for o in others
        if o.accountId != t.accountId
        and o.id != t.id
        and o.transferId is None
        and o.amount == -t.amount
        and abs((o.date - t.date).days) <= DAYS
    ]


def best(t, others: list):
    """The closest in date; none when two are equally close (the user picks by hand)."""
    found = sorted(candidates(t, others), key=lambda o: abs((o.date - t.date).days))
    if not found or t.amount == 0:
        return None
    if len(found) > 1 and abs((found[1].date - t.date).days) == abs((found[0].date - t.date).days):
        return None
    return found[0]


def window(t) -> tuple[dt.date, dt.date]:
    return t.date - dt.timedelta(days=DAYS), t.date + dt.timedelta(days=DAYS)
