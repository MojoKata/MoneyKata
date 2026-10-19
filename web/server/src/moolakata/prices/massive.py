"""Massive, formerly Polygon.io (requirements S4.3, S4.5): option contracts' daily closes, by
their OCC ticker (O:MSFT261120P00480000). A free key; the free plan serves end-of-day options
data at 5 requests a minute."""

import datetime as dt
from decimal import Decimal
from urllib.parse import quote

from .base import Ref, SourceError, TickerSource, register

API = "https://api.polygon.io"


@register
class Massive(TickerSource):
    name = "massive"
    label = "Massive (Polygon.io)"
    classes = frozenset({"option"})
    needs_key = True
    key_url = "https://massive.com/dashboard/api-keys"
    limits = ((5, 60),)
    hosts = ("api.polygon.io",)
    terms = (
        "Free plan: end-of-day option prices, 5 requests a minute, for personal use. An "
        "option's ticker is its OCC symbol."
    )
    terms_checked = dt.date(2026, 10, 1)

    def history(self, ref: Ref, start: dt.date, end: dt.date) -> list[tuple[dt.date, Decimal]]:
        if not self.key:
            raise SourceError("Massive needs its API key")
        url = (
            f"{API}/v2/aggs/ticker/{quote(ref.symbol)}/range/1/day/{start.isoformat()}/"
            f"{end.isoformat()}?adjusted=true&sort=asc&limit=5000&apiKey={quote(self.key)}"
        )
        body = self.get_json(url) or {}
        out = []
        for row in body.get("results") or []:
            day = dt.datetime.fromtimestamp(row["t"] / 1000, dt.UTC).date()
            out.append((day, Decimal(str(row["c"]))))
        return sorted(out)
