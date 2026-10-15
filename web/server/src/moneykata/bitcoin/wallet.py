"""A wallet account's keys and the addresses it watches (requirements S1.6.1): the keys entered
are stored, and each key's addresses derived on the receive and change chains until `gapLimit`
in a row are unused."""

from sqlalchemy import delete, false, func, select
from sqlalchemy.orm import Session

from .. import clock, ids
from ..store.entities.accounts import WalletAddress, WalletKey
from . import keys as bk


def keys_of(s: Session, account_id: str) -> list[WalletKey]:
    return list(
        s.scalars(
            select(WalletKey)
            .where(WalletKey.accountId == account_id, WalletKey.deleted == false())
            .order_by(WalletKey.createdAt, WalletKey.id)
        )
    )


def addresses_of(s: Session, account_id: str) -> list[WalletAddress]:
    return list(
        s.scalars(
            select(WalletAddress)
            .where(WalletAddress.accountId == account_id)
            .order_by(WalletAddress.keyId, WalletAddress.chain, WalletAddress.idx)
        )
    )


def replace(s: Session, account_id: str, entries: list[bk.Entry], gap: int, user_id: str) -> None:
    """The wallet's keys made these: new ones added, missing ones deleted with their addresses,
    and every key's gap limit set."""
    now = clock.now()
    current = {k.value: k for k in keys_of(s, account_id)}
    wanted = {e.value for e in entries}
    for value, k in current.items():
        if value not in wanted:
            k.mark_deleted(user_id, now)
            s.execute(delete(WalletAddress).where(WalletAddress.keyId == k.id))
    for e in entries:
        k = current.get(e.value)
        if k is None:
            k = WalletKey(
                id=ids.new_id("WKey"),
                accountId=account_id,
                kind=e.kind,
                value=e.value,
                script=e.script,
                gapLimit=gap,
            )
            s.add(k)
        elif k.gapLimit != gap:
            k.gapLimit = gap
    s.flush()
    for k in keys_of(s, account_id):
        extend(s, k)


def extend(s: Session, k: WalletKey) -> int:
    """Derive the key's addresses until `gapLimit` past the last used one on each chain; a
    typed address is its own one address. Returns how many were added."""
    now = clock.now()
    if k.kind == "address":
        have = s.scalar(
            select(func.count()).select_from(WalletAddress).where(WalletAddress.keyId == k.id)
        )
        if not have:
            s.add(
                WalletAddress(
                    id=ids.new_id("WAddr"),
                    accountId=k.accountId,
                    keyId=k.id,
                    address=k.value,
                    chain=None,
                    idx=None,
                    createdAt=now,
                )
            )
            s.flush()
            return 1
        return 0
    if k.kind == "descriptor":
        from . import descriptor

        d = descriptor.parse(k.value)
        chains, address = d.chains, d.address
    else:
        xk = bk.extended(k.value)
        chains = (0, 1)

        def address(chain: int, i: int) -> str:
            return bk.address_of(xk.child(chain).child(i).key, xk.script)

    added = 0
    for chain in chains:
        rows = list(
            s.scalars(
                select(WalletAddress).where(
                    WalletAddress.keyId == k.id, WalletAddress.chain == chain
                )
            )
        )
        last_used = max((r.idx for r in rows if r.used), default=-1)
        top = max((r.idx for r in rows), default=-1)
        for i in range(top + 1, last_used + k.gapLimit + 1):
            s.add(
                WalletAddress(
                    id=ids.new_id("WAddr"),
                    accountId=k.accountId,
                    keyId=k.id,
                    address=address(chain, i),
                    chain=chain,
                    idx=i,
                    createdAt=now,
                )
            )
            added += 1
    s.flush()
    return added
