"""A self-custody wallet's keys and addresses (requirements S1.6.1, S1.6.3): public data only.
The form's text is checked for anything that looks like a private key or seed phrase before
anything else, and a refusal never repeats or logs it."""

import datetime as dt

from fastapi import APIRouter, Depends, Request

from .. import access, activity
from ..bitcoin import keys as bk
from ..bitcoin import wallet
from ..errors import Problem, refuse
from .conventions import Model
from .deps import Caller, caller, server
from .prices import apply_egress

router = APIRouter(prefix="/ui/api", tags=["wallets"])
SHOWN = 10  # unused addresses shown a chain


class WalletKeyOut(Model):
    id: str
    kind: str  # xpub or address
    value: str
    script: str
    gapLimit: int
    addresses: int
    used: int


class WalletAddressOut(Model):
    address: str
    keyId: str
    chain: int | None  # 0 receive, 1 change, null typed
    index: int | None
    used: bool
    txCount: int
    balanceSats: int
    checkedAt: dt.datetime | None


class WalletView(Model):
    keys: list[WalletKeyOut]
    addresses: list[WalletAddressOut]
    watched: int  # every address watched
    used: int
    balanceSats: int
    checkedAt: dt.datetime | None


class WalletIn(Model):
    text: str  # extended public keys and addresses, one a line
    gapLimit: int = 20


def _wallet_account(s, c: Caller, account_id: str, level: str):
    a, lv = access.account(s, c.id, account_id, level)
    if a.type != "crypto-wallet":
        raise refuse(None, "not-a-wallet", "Only a self-custody wallet holds keys and addresses.")
    return a, lv


def _view(s, account_id: str) -> WalletView:
    keys = wallet.keys_of(s, account_id)
    rows = wallet.addresses_of(s, account_id)
    shown = []
    for k in keys:
        mine = [r for r in rows if r.keyId == k.id]
        for chain in (None, 0, 1):
            on = [r for r in mine if r.chain == chain]
            last = max((r.idx for r in on if r.used and r.idx is not None), default=-1)
            shown += [r for r in on if r.used or r.chain is None or (r.idx or 0) <= last + SHOWN]
    return WalletView(
        keys=[
            WalletKeyOut(
                id=k.id,
                kind=k.kind,
                value=k.value,
                script=k.script,
                gapLimit=k.gapLimit,
                addresses=sum(1 for r in rows if r.keyId == k.id),
                used=sum(1 for r in rows if r.keyId == k.id and r.used),
            )
            for k in keys
        ],
        addresses=[
            WalletAddressOut(
                address=r.address,
                keyId=r.keyId,
                chain=r.chain,
                index=r.idx,
                used=r.used,
                txCount=r.txCount,
                balanceSats=r.balanceSats,
                checkedAt=r.checkedAt,
            )
            for r in shown
        ],
        watched=len(rows),
        used=sum(1 for r in rows if r.used),
        balanceSats=sum(r.balanceSats for r in rows),
        checkedAt=max((r.checkedAt for r in rows if r.checkedAt), default=None),
    )


@router.get("/accounts/{account_id}/wallet", response_model=WalletView)
def get_wallet(account_id: str, request: Request, c: Caller = Depends(caller)):
    with server(request).db.read() as s:
        _wallet_account(s, c, account_id, "read")
        return _view(s, account_id)


@router.put("/accounts/{account_id}/wallet", response_model=WalletView)
def put_wallet(account_id: str, body: WalletIn, request: Request, c: Caller = Depends(caller)):
    """The wallet's keys and addresses, replaced whole."""
    what = bk.secret_kind(body.text)
    if what:
        raise refuse("text", "secret-refused", bk.REFUSAL.format(what=what))
    try:
        entries = bk.parse(body.text)
    except bk.Refused as e:
        raise refuse("text", e.code, e.message) from None
    if not 1 <= body.gapLimit <= 200:
        raise refuse("gapLimit", "gap-invalid", "From 1 to 200 unused addresses: 20 is usual.")
    with server(request).db.tx() as s:
        a, _ = _wallet_account(s, c, account_id, "write")
        wallet.replace(s, a.id, entries, body.gapLimit, c.id)
        activity.record(
            s,
            "wallet.changed",
            actor=c.id,
            subject_kind="account",
            subject_id=a.id,
            owner=a.ownerId,
        )
        out = _view(s, a.id)
    apply_egress(server(request))
    return out


class SyncOut(Model):
    recorded: int  # transactions added
    wallet: WalletView


@router.post("/accounts/{account_id}/wallet/sync", response_model=SyncOut)
def sync_wallet(account_id: str, request: Request, c: Caller = Depends(caller)):
    """Read the wallet from the explorer or node now (S1.6.2)."""
    from ..bitcoin import sync
    from ..bitcoin.sources import SourceError

    srv = server(request)
    with srv.db.read() as s:
        a, _ = _wallet_account(s, c, account_id, "write")
    try:
        made = sync.sync_account(srv, a.id)
    except SourceError as e:
        raise Problem(502, "source-failed", str(e)) from None
    with srv.db.read() as s:
        return SyncOut(recorded=made, wallet=_view(s, a.id))
