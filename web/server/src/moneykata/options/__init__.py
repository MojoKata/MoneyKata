"""Options (requirements S3.2–S3.4, S3.6): contracts as instruments, and what a trade's cash
comes to."""

import datetime as dt
from decimal import Decimal

from sqlalchemy import false, select
from sqlalchemy.orm import Session

from .. import ids
from ..store.entities.accounts import Instrument, OptionContract
from ..store.repos import ledger as repo

ACTIONS = ("buy-to-open", "sell-to-open", "buy-to-close", "sell-to-close")
CENT = Decimal("0.01")


def symbol(underlying: str, expiry: dt.date, right: str, strike: Decimal) -> str:
    """A contract's symbol as people read it: MSFT 20NOV26 480 P."""
    k = f"{strike.normalize():f}"
    return f"{underlying} {expiry:%d%b%y}".upper() + f" {k} {'C' if right == 'call' else 'P'}"


def contract_of(s: Session, instrument_id: str) -> OptionContract | None:
    return s.scalars(
        select(OptionContract).where(
            OptionContract.instrumentId == instrument_id, OptionContract.deleted == false()
        )
    ).first()


def contract(
    s: Session,
    underlying: str,
    right: str,
    strike: Decimal,
    expiry: dt.date,
    multiplier: int = 100,
) -> tuple[Instrument, OptionContract]:
    """The option instrument for these terms, made the first time."""
    under = repo.instrument(s, underlying, None, "equity")
    sym = symbol(under.symbol, expiry, right, strike)
    inst = repo.instrument(s, sym, None, "option")
    c = contract_of(s, inst.id)
    if c is None:
        c = OptionContract(
            id=ids.new_id("OptCt"),
            instrumentId=inst.id,
            underlyingId=under.id,
            right=right,
            strike=strike,
            expiry=expiry,
            multiplier=multiplier,
        )
        s.add(c)
        s.flush()
    if not inst.name:
        inst.name = (
            f"{under.symbol} {'call' if right == 'call' else 'put'} {strike.normalize():f}, "
            f"expiring {expiry:%b %-d, %Y}"
        )
    return inst, c


def cash(action: str, contracts: Decimal, premium: Decimal, fees: Decimal, mult: int) -> Decimal:
    """What a trade does to the account's cash: paid out to buy, received to sell, less fees."""
    gross = (contracts * premium * mult).quantize(CENT)
    if action in ("buy-to-open", "buy-to-close"):
        return -gross - fees
    return gross - fees
