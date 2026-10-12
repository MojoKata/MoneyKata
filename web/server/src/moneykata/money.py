"""Exact amounts (requirements §17.3): Decimal in Python, strings in JSON, integer cents or
decimal text in SQLite. Floats are refused at the edge."""

import decimal
from decimal import ROUND_HALF_EVEN, Decimal

CONTEXT = decimal.Context(prec=34, rounding=ROUND_HALF_EVEN)
decimal.setcontext(CONTEXT)
decimal.DefaultContext.prec = 34
decimal.DefaultContext.rounding = ROUND_HALF_EVEN

CENT = Decimal("0.01")
QUANTITY_PLACES = 18
QUANTUM = Decimal(1).scaleb(-QUANTITY_PLACES)
ZERO = Decimal(0)


class AmountError(ValueError):
    pass


def parse(value: object, places: int | None = None) -> Decimal:
    """A decimal from its JSON form, a string. Floats and other types are refused; so are
    NaN, infinities and more places than allowed."""
    if isinstance(value, bool) or not isinstance(value, str | int | Decimal):
        raise AmountError('amounts are decimal strings, such as "1234.50"')
    try:
        d = value if isinstance(value, Decimal) else Decimal(str(value).strip())
    except decimal.InvalidOperation:
        raise AmountError(f"{value!r} is not a number") from None
    if not d.is_finite():
        raise AmountError("amounts must be finite")
    if places is not None and d.as_tuple().exponent < -places:  # type: ignore[operator]
        raise AmountError(f"at most {places} decimal places")
    return d


def to_cents(d: Decimal) -> int:
    q = d.quantize(CENT, rounding=ROUND_HALF_EVEN, context=CONTEXT)
    return int(q * 100)


def from_cents(cents: int | None) -> Decimal | None:
    return None if cents is None else (Decimal(cents) / 100).quantize(CENT)


def money_str(d: Decimal | None) -> str | None:
    """Dollars with two places: "1234.50"."""
    return None if d is None else str(d.quantize(CENT, rounding=ROUND_HALF_EVEN, context=CONTEXT))


def cents_str(cents: int | None) -> str | None:
    return None if cents is None else money_str(Decimal(cents) / 100)


def quantity(d: Decimal) -> Decimal:
    """A quantity or price at its fixed scale of 18 places."""
    return d.quantize(QUANTUM, rounding=ROUND_HALF_EVEN, context=CONTEXT)


def quantity_str(d: Decimal | None) -> str | None:
    """A quantity or price to its own scale: no trailing zeros beyond what it carries."""
    if d is None:
        return None
    text = format(d.normalize(CONTEXT), "f")
    return text if text not in ("-0",) else "0"
