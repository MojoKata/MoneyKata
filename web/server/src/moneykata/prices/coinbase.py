"""Coinbase's public prices (requirements S4.3): major coins in US dollars, with no key."""

import datetime as dt
from decimal import Decimal
from urllib.parse import quote

from .. import clock
from .base import Ref, TickerSource, register

EXCHANGE = "https://api.exchange.coinbase.com"
CANDLES_PER_CALL = 300


@register
class Coinbase(TickerSource):
    name = "coinbase"
    label = "Coinbase"
    classes = frozenset({"crypto"})
    limits = ((10, 1),)
    hosts = ("api.exchange.coinbase.com",)
    terms = "Public market data, no key. Daily candles close at 00:00 UTC."
    terms_checked = dt.date(2026, 10, 1)

    def history(self, ref: Ref, start: dt.date, end: dt.date) -> list[tuple[dt.date, Decimal]]:
        product = quote(f"{ref.symbol.upper()}-USD")
        out: dict[dt.date, Decimal] = {}
        # Today's candle (in UTC) is still open: its close is the latest trade, an intraday
        # quote (S4.4). Stored, it would never be replaced, as refreshes start after it.
        end = min(end, clock.today() - dt.timedelta(days=1))
        cursor = start
        while cursor <= end:
            stop = min(end, cursor + dt.timedelta(days=CANDLES_PER_CALL - 1))
            url = (
                f"{EXCHANGE}/products/{product}/candles?granularity=86400"
                f"&start={cursor.isoformat()}T00:00:00Z&end={stop.isoformat()}T23:59:59Z"
            )
            rows = self.get_json(url) or []
            for row in rows:  # [time, low, high, open, close, volume]
                day = dt.datetime.fromtimestamp(row[0], dt.UTC).date()
                if day <= end:
                    out[day] = Decimal(str(row[4]))
            cursor = stop + dt.timedelta(days=1)
        return sorted(out.items())
