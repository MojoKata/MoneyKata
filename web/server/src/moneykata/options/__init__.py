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


# ---------- expiry, assignment and exercise (S3.4, S3.6) ----------


def open_basis(replay, instrument_id: str, contracts: Decimal) -> tuple[Decimal, Decimal | None]:
    """The open quantity and the basis that goes with this many contracts (a short position's
    basis is its credit, negative)."""
    lots = [x for x in replay.open if x.instrumentId == instrument_id and x.quantity]
    held = sum((x.quantity for x in lots), Decimal(0))
    if not held:
        return held, None
    if any(x.basis is None for x in lots):
        return held, None
    total = sum((x.basis for x in lots), Decimal(0))
    return held, (total * contracts / abs(held)).quantize(CENT)


def settle(s: Session, user_id: str, account, inst, how: str, day: dt.date, contracts=None):
    """Record an option's end: expired, assigned (a short one) or exercised (a long one). An
    assignment or exercise also makes the stock trade at the strike, with the premium folded
    into its basis or proceeds as the IRS rules say (S3.4); returns the transactions made."""
    from ..errors import refuse
    from ..store.entities.accounts import Lot, Transaction

    c = contract_of(s, inst.id)
    if c is None:
        raise refuse("instrumentId", "not-an-option", "That isn't an option.")
    replay = repo.load(s, account).replay()
    held = replay.quantity(inst.id)
    if not held:
        raise refuse("instrumentId", "nothing-open", "Nothing of it is open in this account.")
    n = Decimal(contracts) if contracts else abs(held)
    if n <= 0 or n > abs(held):
        raise refuse("contracts", "contracts-invalid", f"Up to {abs(held)} contracts.")
    if how == "exercise" and held < 0:
        raise refuse("how", "short-exercise", "A short option is assigned, not exercised.")
    if how == "assign" and held > 0:
        raise refuse("how", "long-assign", "A long option is exercised, not assigned.")
    _, basis = open_basis(replay, inst.id, n)
    made = []
    end = Transaction(
        id=ids.new_id("Txn"),
        accountId=account.id,
        date=day,
        kind=how if how != "expired" else "expire",
        amount=Decimal(0),
        payee=f"{({'expired': 'Expired', 'assign': 'Assigned', 'exercise': 'Exercised'})[how]} "
        f"{inst.symbol}",
        instrumentId=inst.id,
        quantity=n,
        createdById=user_id,
    )
    s.add(end)
    s.flush()
    made.append(end)
    if how == "expired":
        return made
    shares = n * c.multiplier
    cash = (c.strike * shares).quantize(CENT)
    under = s.get(Instrument, c.underlyingId)
    buys = (how == "exercise" and c.right == "call") or (how == "assign" and c.right == "put")
    stock = Transaction(
        id=ids.new_id("Txn"),
        accountId=account.id,
        date=day,
        kind="buy" if buys else "sell",
        amount=-cash if buys else cash,
        payee=f"{'Buy' if buys else 'Sell'} {under.symbol} at {c.strike.normalize():f} "
        f"({'assigned' if how == 'assign' else 'exercised'})",
        instrumentId=under.id,
        quantity=shares,
        price=c.strike,
        lotMethod=None if buys else account.lotMethod,
        optionTransactionId=end.id,
        createdById=user_id,
    )
    if not buys and basis is not None:
        # A short call's credit adds to the proceeds; a long put's premium comes off them.
        stock.proceedsAdjustment = -basis
    s.add(stock)
    s.flush()
    if buys:
        # A long call's premium adds to the stock's basis; a short put's credit comes off it.
        s.add(
            Lot(
                id=ids.new_id("Lot"),
                accountId=account.id,
                instrumentId=under.id,
                transactionId=stock.id,
                acquiredOn=day,
                quantity=shares,
                costBasis=cash + (basis or Decimal(0)),
                basisMissing=False,
            )
        )
    made.append(stock)
    return made


def expire_due(s: Session, today: dt.date) -> int:
    """Options past their expiry the underlying's close left out of the money expire the day
    after (S3.6); those in the money, or without a close, wait for the user."""
    from .. import valuation
    from ..ledger import types as atypes
    from ..store.entities.accounts import Account

    done = 0
    for a in s.scalars(select(Account).where(Account.deleted == false())):
        if not atypes.investing(a.type):
            continue
        replay = repo.load(s, a).replay()
        for iid in replay.positions():
            c = contract_of(s, iid)
            if c is None or c.expiry >= today:
                continue
            close = valuation.prices(s, [c.underlyingId], c.expiry).get(c.underlyingId)
            if close is None or close.asOf < c.expiry - dt.timedelta(days=4):
                continue
            if in_the_money(c, close.price):
                continue
            settle(s, a.ownerId, a, s.get(Instrument, iid), "expired", c.expiry)
            done += 1
    return done


def in_the_money(c: OptionContract, price: Decimal) -> bool:
    return price > c.strike if c.right == "call" else price < c.strike
