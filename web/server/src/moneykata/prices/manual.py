"""Manual prices (requirements §7.3): for what has no free ticker (529 portfolios, 401(k)
collective trusts, single bonds), a value from a statement or a typed price with its date.
Nothing is fetched; typed prices are stored as closes with the source "manual"."""

import datetime as dt
from decimal import Decimal

from .base import Ref, TickerSource, register


@register
class Manual(TickerSource):
    name = "manual"
    label = "Manual"
    classes = frozenset(
        {
            "equity",
            "etf",
            "mutual-fund",
            "money-market",
            "bond",
            "option",
            "crypto",
            "metal",
            "other",
        }
    )
    fetches = False
    terms = "Typed prices and statement values; a statement value over 90 days old is stale."

    def history(self, ref: Ref, start: dt.date, end: dt.date) -> list[tuple[dt.date, Decimal]]:
        return []
