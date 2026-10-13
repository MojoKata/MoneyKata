"""The dev stub (requirements S17.7): deterministic random walks for every class, so dev mode
never calls a real provider. Available only in dev mode."""

import datetime as dt
import hashlib
import math
from decimal import Decimal

from .. import clock
from .base import Ref, TickerSource, register

START = dt.date(2020, 1, 1)


def _seed(symbol: str) -> int:
    return int.from_bytes(hashlib.sha256(symbol.encode()).digest()[:4])


def walk(symbol: str, day: dt.date) -> Decimal:
    """The same price for the same symbol and day, every time."""
    seed = _seed(symbol)
    base = 20 + seed % 480
    n = (day - START).days
    drift = 0.00025 + (seed % 7) * 0.00003
    wave = math.sin(n / (17 + seed % 23)) * 0.04 + math.sin(n / (61 + seed % 31)) * 0.07
    noise = ((n * 2654435761 + seed) % 1000 - 500) / 50000
    return Decimal(str(round(base * math.exp(drift * n + wave + noise), 2)))


@register
class Stub(TickerSource):
    name = "stub"
    label = "Dev stub"
    classes = frozenset({"equity", "etf", "mutual-fund", "bond", "crypto", "metal", "other"})
    terms = "Dev mode only: made-up prices."
    dev_only = True

    def history(self, ref: Ref, start: dt.date, end: dt.date) -> list[tuple[dt.date, Decimal]]:
        out = []
        day = start
        trading = ref.instrumentClass == "crypto"
        # A close exists once its market day has closed: today's comes tomorrow.
        end = min(end, clock.today() - dt.timedelta(days=0 if trading else 1))
        while day <= end:
            if trading or day.weekday() < 5:
                out.append((day, walk(ref.symbol, day)))
            day += dt.timedelta(days=1)
        return out
