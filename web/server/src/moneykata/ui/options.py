"""Option trades (requirements S3.2, S3.3): the four opening and closing trades, recorded with
the contract they are in."""

import datetime as dt
from decimal import Decimal

from fastapi import APIRouter, Depends, Request

from .. import access, activity, ids, options
from ..errors import FieldError, Problem, refuse
from ..ledger import types as atypes
from ..store.entities.accounts import Transaction
from ..store.repos import ledger as repo
from .conventions import Model, Money, Quantity
from .deps import Caller, caller, server
from .transactions import TxnOut, shape

router = APIRouter(prefix="/ui/api", tags=["options"])


class OptionTrade(Model):
    date: dt.date
    action: str  # buy-to-open, sell-to-open, buy-to-close, sell-to-close
    underlying: str
    right: str  # call or put
    strike: Quantity
    expiry: dt.date
    contracts: Quantity
    premium: Quantity  # a share
    fees: Money = Decimal(0)
    multiplier: int = 100


@router.post("/accounts/{account_id}/options", response_model=TxnOut, status_code=201)
def record_trade(account_id: str, body: OptionTrade, request: Request, c: Caller = Depends(caller)):
    e: list[FieldError] = []
    if body.action not in options.ACTIONS:
        e.append(FieldError("action", "action-invalid", "Buy or sell, to open or to close."))
    if body.right not in ("call", "put"):
        e.append(FieldError("right", "right-invalid", "A call or a put."))
    underlying = body.underlying.strip().upper()
    if not underlying or len(underlying) > 12:
        e.append(FieldError("underlying", "symbol-invalid", "The underlying's symbol: MSFT."))
    if body.strike <= 0:
        e.append(FieldError("strike", "strike-invalid", "More than zero."))
    if body.contracts <= 0 or body.contracts != body.contracts.to_integral_value():
        e.append(FieldError("contracts", "contracts-invalid", "A whole number of contracts."))
    if body.premium < 0:
        e.append(FieldError("premium", "premium-invalid", "Zero or more, a share."))
    if body.fees < 0:
        e.append(FieldError("fees", "fees-invalid", "Zero or more."))
    if body.action.endswith("to-open") and body.expiry < body.date:
        e.append(FieldError("expiry", "expired", "It expired before the trade."))
    if not 1 <= body.multiplier <= 10000:
        e.append(FieldError("multiplier", "multiplier-invalid", "Shares a contract: 100."))
    if e:
        raise Problem(422, e[0].code, e[0].message, e)
    with server(request).db.tx() as s:
        a, level = access.account(s, c.id, account_id, "write")
        if not atypes.investing(a.type):
            raise refuse(
                "action", "kind-not-for-account", "Options belong in an investing account."
            )
        inst, contract = options.contract(
            s, underlying, body.right, body.strike, body.expiry, body.multiplier
        )
        if body.action.endswith("to-close"):
            held = repo.load(s, a).replay().quantity(inst.id)
            want_long = body.action == "sell-to-close"
            if (want_long and held < body.contracts) or (not want_long and -held < body.contracts):
                raise refuse(
                    "contracts",
                    "nothing-to-close",
                    f"The account holds {abs(held)} {'long' if held >= 0 else 'short'} "
                    "contracts of it.",
                )
        t = Transaction(
            id=ids.new_id("Txn"),
            accountId=a.id,
            date=body.date,
            kind=body.action,
            amount=options.cash(
                body.action, body.contracts, body.premium, body.fees, contract.multiplier
            ),
            payee=f"{body.action.replace('-', ' ').capitalize()} {inst.symbol}",
            instrumentId=inst.id,
            quantity=body.contracts,
            price=body.premium,
            fees=body.fees or None,
            createdById=c.id,
        )
        s.add(t)
        s.flush()
        activity.record(
            s,
            "option.traded",
            actor=c.id,
            subject_kind="account",
            subject_id=a.id,
            owner=a.ownerId,
        )
        return shape(s, c.id, [t], {a.id: level})[0]
