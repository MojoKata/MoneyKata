"""CBOE's delayed quotes (requirements S4.3, S4.5): the whole option chain of an underlying in
one answer, 15 minutes delayed, from the JSON behind cboe.com's quote pages. No key. It isn't
an official API: CBOE offers it for personal, non-commercial use, and may change it. Asked
once a day after the close, one request per underlying, every held contract on it marked from
that one answer."""

import datetime as dt
from decimal import ROUND_HALF_EVEN, Decimal

from .base import Ref, SourceError, TickerSource, register

API = "https://cdn-api.cboe.com/api/global/delayed_quotes/options"
CENT = Decimal("0.01")

# Index options are listed under the index's chain, `_SPX`, whose weeklies (and PM-settled
# contracts) carry their own root: an SPX contract may be SPX or SPXW (S3.2).
INDEXES = {
    "SPX": ("_SPX", ("SPX", "SPXW")),
    "NDX": ("_NDX", ("NDX", "NDXP")),
    "RUT": ("_RUT", ("RUT", "RUTW")),
    "VIX": ("_VIX", ("VIX", "VIXW")),
    "XSP": ("_XSP", ("XSP",)),
    "DJX": ("_DJX", ("DJX",)),
}
# A contract an import names by its weekly root is in the same chain.
INDEXES |= {w: (chain, (w,)) for chain, roots in list(INDEXES.values()) for w in roots[1:]}


def split_occ(ticker: str) -> tuple[str, str]:
    """`O:MSFT261120P00480000` as its root and the 15 characters after it (expiry, side and
    strike)."""
    occ = ticker.removeprefix("O:")
    if len(occ) < 16:
        raise SourceError(f"{ticker} is not an OCC option ticker")
    return occ[:-15], occ[-15:]


def mark(row: dict) -> Decimal | None:
    """A contract's mark: the middle of the bid and the ask when both are quoted, else the
    last trade's price, rounded to the cent."""
    bid, ask = Decimal(str(row.get("bid") or 0)), Decimal(str(row.get("ask") or 0))
    if bid > 0 and ask >= bid:
        return ((bid + ask) / 2).quantize(CENT, rounding=ROUND_HALF_EVEN)
    last = Decimal(str(row.get("last_trade_price") or 0))
    return last.quantize(CENT, rounding=ROUND_HALF_EVEN) if last > 0 else None


@register
class Cboe(TickerSource):
    name = "cboe"
    label = "CBOE delayed quotes"
    classes = frozenset({"option"})
    limits = ((30, 60),)
    hosts = ("cdn-api.cboe.com",)
    terms = (
        "Not an official API: the delayed quotes behind cboe.com's pages, 15 minutes "
        "delayed, which CBOE offers for personal, non-commercial use and may change. One "
        "request per underlying, after the close."
    )
    terms_checked = dt.date(2026, 10, 14)

    def __init__(self, *args, **kw) -> None:
        super().__init__(*args, **kw)
        self._chains: dict[str, tuple[dt.date, dict[str, dict]]] = {}

    def chain(self, chain: str) -> tuple[dt.date, dict[str, dict]]:
        """An underlying's chain, fetched once for every contract on it: the market day it is
        from, and each contract's row by its OCC symbol."""
        if chain not in self._chains:
            body = self.get_json(f"{API}/{chain}.json")
            data = (body or {}).get("data") or {}
            when = data.get("last_trade_time") or (body or {}).get("timestamp") or ""
            try:
                day = dt.date.fromisoformat(when[:10])
            except ValueError:
                raise SourceError(f"{self.label} answered without a date for {chain}") from None
            self._chains[chain] = (day, {r["option"]: r for r in data.get("options") or []})
        return self._chains[chain]

    def history(self, ref: Ref, start: dt.date, end: dt.date) -> list[tuple[dt.date, Decimal]]:
        """Only the latest close: CBOE gives the chain as it is now, not its history."""
        root, rest = split_occ(ref.symbol)
        chain, roots = INDEXES.get(root, (root, (root,)))
        day, rows = self.chain(chain)
        if not start <= day <= end:
            return []
        for r in roots:
            row = rows.get(r + rest)
            if row is not None:
                price = mark(row)
                return [(day, price)] if price is not None else []
        return []
