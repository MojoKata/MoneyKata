"""Dev mode's options (requirements S17.7): in Alice's taxable brokerage, a covered call
written and bought back, a cash-secured put still open, and a call bought and sold."""

import datetime as dt
from decimal import Decimal as D

from sqlalchemy import select

from .. import clock, ids, options
from ..store.entities.accounts import Account, Transaction


def seed_options(s, people: dict) -> None:
    brk = s.scalars(select(Account).where(Account.name == "Taxable brokerage")).first()
    if brk is None:
        return
    today = clock.today()
    alice = people["alice"]

    def trade(days_ago, action, under, right, strike, expiry, contracts, premium, fees="0.65"):
        inst, c = options.contract(s, under, right, D(strike), expiry)
        day = today - dt.timedelta(days=days_ago)
        s.add(
            Transaction(
                id=ids.new_id("Txn"),
                accountId=brk.id,
                date=day,
                kind=action,
                amount=options.cash(action, D(contracts), D(premium), D(fees), c.multiplier),
                payee=f"{action.replace('-', ' ').capitalize()} {inst.symbol}",
                instrumentId=inst.id,
                quantity=D(contracts),
                price=D(premium),
                fees=D(fees),
                createdById=alice.id,
            )
        )

    month = today + dt.timedelta(days=37)
    gone = today - dt.timedelta(days=20)
    trade(80, "sell-to-open", "VTI", "call", "320", gone, "1", "4.10")
    trade(45, "buy-to-close", "VTI", "call", "320", gone, "1", "1.25")
    trade(30, "sell-to-open", "MSFT", "put", "480", month, "2", "6.40")
    trade(60, "buy-to-open", "AAPL", "call", "250", today + dt.timedelta(days=90), "2", "5.20")
    trade(15, "sell-to-close", "AAPL", "call", "250", today + dt.timedelta(days=90), "1", "7.80")
    s.flush()
