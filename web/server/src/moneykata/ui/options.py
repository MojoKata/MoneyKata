"""Option trades (requirements S3.2, S3.3): the four opening and closing trades, recorded with
the contract they are in."""

import datetime as dt
from decimal import Decimal

from fastapi import APIRouter, Depends, Request

from .. import access, activity, ids, options, washes
from ..errors import FieldError, Problem, refuse
from ..ledger import types as atypes
from ..store.entities.accounts import Instrument, Transaction
from ..store.repos import ledger as repo
from ..taxes import closed
from .conventions import ExactRoute, Model, Money, Quantity
from .deps import Caller, caller, server
from .transactions import TxnOut, shape

router = APIRouter(prefix="/ui/api", route_class=ExactRoute, tags=["options"])


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
def record_trade(
    account_id: str,
    body: OptionTrade,
    request: Request,
    c: Caller = Depends(caller),
    confirm: bool = False,
):
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
        guard = closed.Guard(s, a, confirm)
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
        guard.check()
        activity.record(
            s,
            "option.traded",
            actor=c.id,
            subject_kind="account",
            subject_id=a.id,
            owner=a.ownerId,
        )
        return shape(s, c.id, [t], {a.id: level})[0]


class Settle(Model):
    how: str  # expired, assign, exercise
    date: dt.date
    contracts: Quantity | None = None


@router.post(
    "/accounts/{account_id}/options/{instrument_id}/settle",
    response_model=list[TxnOut],
    status_code=201,
)
def settle(
    account_id: str,
    instrument_id: str,
    body: Settle,
    request: Request,
    c: Caller = Depends(caller),
    confirm: bool = False,
):
    """An option's end: it expired, was assigned, or was exercised (S3.4, S3.6)."""
    if body.how not in ("expired", "assign", "exercise"):
        raise refuse("how", "how-invalid", "Expired, assigned or exercised.")
    with server(request).db.tx() as s:
        a, level = access.account(s, c.id, account_id, "write")
        inst = s.get(Instrument, instrument_id)
        if inst is None or inst.deleted:
            raise refuse("instrumentId", "not-found", "No such option.")
        guard = closed.Guard(s, a, confirm)
        made = options.settle(s, c.id, a, inst, body.how, body.date, body.contracts)
        washes.recompute(s, a.ownerId)
        guard.check()
        activity.record(
            s,
            "option.settled",
            actor=c.id,
            subject_kind="account",
            subject_id=a.id,
            owner=a.ownerId,
        )
        return shape(s, c.id, made, {a.id: level})


# ---- Adjusted contracts (S3.10.2) ----


class OpenContract(Model):
    instrumentId: str
    symbol: str
    right: str
    strike: Quantity
    expiry: dt.date
    root: str | None
    held: list[str]  # the accounts it is open in, with how many: "Short 2 in Options"


class Adjustable(Model):
    underlying: str
    underlyingId: str
    contracts: list[OpenContract]


@router.get("/options/adjustable", response_model=list[Adjustable])
def adjustable(request: Request, c: Caller = Depends(caller)):
    """The caller's open contracts, by underlying, that an adjustment from the OCC's memo can
    change: in the accounts they may change."""
    by: dict[str, dict] = {}
    with server(request).db.read() as s:
        for a, level in access.visible_accounts(s, c.id):
            if level not in ("owner", "write") or not atypes.investing(a.type):
                continue
            for iid, qty in repo.load(s, a).replay().positions().items():
                oc = options.contract_of(s, iid)
                if oc is None:
                    continue
                under = s.get(Instrument, oc.underlyingId)
                group = by.setdefault(
                    under.id, {"underlying": under.symbol, "underlyingId": under.id, "c": {}}
                )
                row = group["c"].setdefault(
                    iid,
                    {
                        "instrumentId": iid,
                        "symbol": s.get(Instrument, iid).symbol,
                        "right": oc.right,
                        "strike": oc.strike,
                        "expiry": oc.expiry,
                        "root": oc.root,
                        "held": [],
                    },
                )
                side = "Short" if qty < 0 else "Long"
                row["held"].append(f"{side} {abs(qty).normalize():f} in {a.name}")
    return [
        Adjustable(
            underlying=g["underlying"],
            underlyingId=g["underlyingId"],
            contracts=[OpenContract(**x) for x in g["c"].values()],
        )
        for g in sorted(by.values(), key=lambda g: g["underlying"])
    ]


class DeliverablePart(Model):
    symbol: str
    shares: Quantity


class ContractAdjustment(Model):
    instrumentId: str
    root: str
    strike: Quantity
    deliverable: list[DeliverablePart]
    cash: Money = Decimal(0)


class Adjustment(Model):
    date: dt.date
    contracts: list[ContractAdjustment]


class Adjusted(Model):
    contracts: int
    accounts: int


@router.post("/options/adjust", response_model=Adjusted)
def adjust_contracts(body: Adjustment, request: Request, c: Caller = Depends(caller)):
    """Each open contract to its new root, strike and deliverable, from the OCC's memo; its
    lots carry over in every account the caller may change, nothing sold (S3.10.2)."""
    from ..options import adjust

    if not body.contracts:
        raise refuse("contracts", "contracts-missing", "At least one contract.")
    moved = 0
    touched: set[str] = set()
    with server(request).db.tx() as s:
        mine = [
            a
            for a, level in access.visible_accounts(s, c.id)
            if level in ("owner", "write") and atypes.investing(a.type)
        ]
        for i, x in enumerate(body.contracts):
            oc = options.contract_of(s, x.instrumentId)
            if oc is None:
                raise refuse(f"contracts.{i}.instrumentId", "not-an-option", "An open contract.")
            root = x.root.strip().upper()
            if not adjust.ADJUSTED_ROOT.match(root) and root != (oc.root or "").upper():
                raise refuse(f"contracts.{i}.root", "root-invalid", "The new root, such as XYZ1.")
            if x.strike <= 0:
                raise refuse(f"contracts.{i}.strike", "strike-invalid", "A strike above 0.")
            parts = adjust.check_deliverable(
                s, [{"symbol": p.symbol, "shares": p.shares} for p in x.deliverable]
            )
            if not parts:
                raise refuse(
                    f"contracts.{i}.deliverable", "deliverable-missing", "What it delivers."
                )
            old = s.get(Instrument, x.instrumentId)
            new, _ = adjust.adjusted_contract(s, oc, root, x.strike, parts, x.cash)
            for a in mine:
                if adjust.carry(s, c.id, a, old, new, Decimal(1), body.date):
                    moved += 1
                    touched.add(a.id)
        for a in mine:
            if a.id in touched:
                activity.record(
                    s,
                    "option.adjusted",
                    actor=c.id,
                    subject_kind="account",
                    subject_id=a.id,
                    owner=a.ownerId,
                )
        s.flush()
        owners = {a.ownerId for a in mine if a.id in touched}
        for o in owners:
            washes.recompute(s, o)
    return Adjusted(contracts=moved, accounts=len(touched))


# ---- Corporate actions (S2.4) ----


class CorporateAction(Model):
    kind: str  # split, symbol-change, spin-off, merger
    date: dt.date
    instrumentId: str
    ratio: Quantity | None = None  # new shares for each one held
    newSymbol: str | None = None
    basisShare: Quantity | None = None  # a spin-off: the percent of basis that moves
    cashPerShare: Money | None = None  # a merger's cash for each share held
    newPrice: Quantity | None = None  # a new share's price that day, for a merger's cash


@router.post(
    "/accounts/{account_id}/corporate-actions", response_model=list[TxnOut], status_code=201
)
def corporate_action(
    account_id: str,
    body: CorporateAction,
    request: Request,
    c: Caller = Depends(caller),
    confirm: bool = False,
):
    """A split, symbol change, spin-off or merger: lots reshaped or moved, never sold and
    bought again; a merger's cash is a gain only as far as the gain goes."""
    from .. import corporate

    if body.kind not in corporate.KINDS:
        raise refuse("kind", "kind-invalid", "A split, symbol change, spin-off or merger.")
    with server(request).db.tx() as s:
        a, level = access.account(s, c.id, account_id, "write")
        if not atypes.investing(a.type):
            raise refuse("kind", "kind-not-for-account", "These belong in an investing account.")
        inst = s.get(Instrument, body.instrumentId)
        if inst is None or inst.deleted or inst.instrumentClass == "option":
            raise refuse("instrumentId", "instrument-unknown", "Choose a holding.")
        guard = closed.Guard(s, a, confirm)
        made = corporate.record(
            s,
            c.id,
            a,
            inst,
            body.kind,
            body.date,
            body.ratio,
            body.newSymbol,
            body.basisShare,
            body.cashPerShare,
            body.newPrice,
        )
        washes.recompute(s, a.ownerId)
        guard.check()
        activity.record(
            s,
            "account.corporate-action",
            actor=c.id,
            subject_kind="account",
            subject_id=a.id,
            owner=a.ownerId,
            detail={"name": corporate.WORDS[body.kind].lower()},
        )
        return shape(s, c.id, made, {a.id: level})
