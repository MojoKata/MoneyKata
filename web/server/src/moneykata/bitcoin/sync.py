"""Keeping wallets current (requirements S1.6.2): every hour, and when asked, each wallet's
addresses are read from the explorer or node; the addresses found used extend the derivation
to keep the gap limit; and each confirmed transaction is recorded once (by its txid) as bitcoin
received (a transfer in, its basis to be entered) or sent (a transfer out, the network fee
included). Nothing is sent to the explorer or node but the addresses or the public keys."""

import datetime as dt
import logging
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import false, select

from .. import clock, ids, settings, timezones
from ..store.entities.accounts import Account, Instrument, Transaction, WalletAddress
from ..store.entities.prices import Price
from ..store.repos import ledger as repo
from ..store.repos import secrets as secret_repo
from . import sources, wallet
from .sources import SAT, Config, SourceError

log = logging.getLogger("moneykata.bitcoin")
PASSWORD = ("Setting", "bitcoin", "password")
ROUNDS = 10  # derivation rounds a sync extends the gap by, at most


def config(s, secrets_key: bytes | None) -> Config:
    get = lambda k: settings.get(s, k)  # noqa: E731
    pw = secret_repo.use(s, secrets_key, *PASSWORD) if secrets_key else None
    return Config(
        kind=get("bitcoinSource"),
        esploraUrl=get("bitcoinEsploraUrl") or sources.DEFAULT_ESPLORA,
        host=get("bitcoinNodeHost"),
        port=get("bitcoinNodePort"),
        tls=get("bitcoinNodeTls"),
        rpcUser=get("bitcoinRpcUser"),
        password=pw,
    )


def source(server, s):
    if server.config.stubs:
        from .stub import Stub

        return Stub()
    return sources.make(config(s, server.keys.secrets), server.guard)


def hosts(s) -> tuple[list[str], list[str]]:
    """The explorer's or node's host, for the egress guard, once a wallet exists."""
    has_wallet = s.scalars(
        select(Account.id).where(Account.type == "crypto-wallet", Account.deleted == false())
    ).first()
    return config(s, None).hosts() if has_wallet else ([], [])


def _scan(src, account_id: str, s) -> tuple[list[sources.Tx], set[str]]:
    rows = wallet.addresses_of(s, account_id)
    if isinstance(src, sources.Core):
        wanted = []
        for k in wallet.keys_of(s, account_id):
            top = max((r.idx for r in rows if r.keyId == k.id and r.idx is not None), default=None)
            wanted += sources.descriptors(k, top)
        name = f"moneykata-{account_id}"
        src.wallet(name, wanted)
        txs, used = src.history_of(name)
        return txs, used | {a for t in txs for a in t.addresses}
    txs = src.history([r.address for r in rows])
    return txs, {a for t in txs for a in t.addresses}


def sync_account(server, account_id: str) -> int:
    """Read one wallet now; returns the transactions recorded. Raises SourceError."""
    with server.db.read() as s:
        src = source(server, s)
    txs: dict[str, sources.Tx] = {}
    for _ in range(ROUNDS):
        with server.db.read() as s:
            found, used = _scan(src, account_id, s)
        txs.update({t.txid: t for t in found})
        with server.db.tx() as s:
            now = clock.now()
            counts: dict[str, int] = {}
            for t in txs.values():
                for a in t.addresses:
                    counts[a] = counts.get(a, 0) + 1
            for r in s.scalars(select(WalletAddress).where(WalletAddress.accountId == account_id)):
                r.used = r.used or r.address in used
                r.txCount = counts.get(r.address, 0)
                r.checkedAt = now
            s.flush()
            added = sum(wallet.extend(s, k) for k in wallet.keys_of(s, account_id))
        if not added:
            break
    with server.db.tx() as s:
        made = record(s, account_id, list(txs.values()))
        unpriced = (
            made
            and not s.scalars(
                select(Price.instrumentId)
                .join(Instrument, Instrument.id == Price.instrumentId)
                .where(Instrument.symbol == "BTC")
            ).first()
        )
    if unpriced:
        server.tasks.run_now("prices")  # the first coins held: their price history (S4.4)
    return made


def record(s, account_id: str, txs: list[sources.Tx]) -> int:
    a = s.get(Account, account_id)
    have = set(
        s.scalars(
            select(Transaction.fitId).where(
                Transaction.accountId == account_id, Transaction.fitId.like("btc:%")
            )
        )
    )
    zone = ZoneInfo(timezones.host_zone())
    btc = repo.instrument(s, "BTC", "Bitcoin", "crypto")
    made = 0
    for t in sorted(txs, key=lambda x: x.confirmedAt or dt.datetime.max.replace(tzinfo=dt.UTC)):
        if t.confirmedAt is None or not t.net or f"btc:{t.txid}" in have:
            continue
        qty = Decimal(abs(t.net)) / SAT
        s.add(
            Transaction(
                id=ids.new_id("Txn"),
                accountId=a.id,
                date=t.confirmedAt.astimezone(zone).date(),
                kind="transfer-in" if t.net > 0 else "transfer-out",
                amount=Decimal(0),
                payee="Received bitcoin" if t.net > 0 else "Sent bitcoin",
                memo=f"txid {t.txid}" + (f" · network fee {t.fee:,} sats" if t.fee else ""),
                instrumentId=btc.id,
                quantity=qty,
                fitId=f"btc:{t.txid}",
            )
        )
        made += 1
    s.flush()
    return made


def sync_all(server, ctx=None) -> str | None:
    """Every wallet, for the hourly task; returns the first error, if any."""
    with server.db.read() as s:
        wallets = list(
            s.scalars(
                select(Account.id).where(
                    Account.type == "crypto-wallet",
                    Account.deleted == false(),
                    Account.active.is_(True),
                )
            )
        )
    error = None
    for account_id in wallets:
        if ctx is not None and ctx.stop.is_set():
            break
        try:
            sync_account(server, account_id)
        except SourceError as e:
            error = error or str(e)
            log.warning("bitcoin: %s", e)
    if error:
        raise SourceError(error)
    return None
