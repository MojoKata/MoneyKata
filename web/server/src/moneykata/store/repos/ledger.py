"""Loading an account's ledger, the shipped categories, instruments, and applying an import
(requirements S1.3, S1.7, S2)."""

import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import false, func, or_, select
from sqlalchemy.orm import Session

from ... import activity, ids
from ...importers.parsed import ParsedFile
from ...ledger import balances, lots, transfers
from ...ledger.categories import DEFAULTS
from ..db import live
from ..entities.accounts import (
    Account,
    Anchor,
    Category,
    Holding,
    Import,
    Instrument,
    Lot,
    LotPick,
    Transaction,
    WashSale,
)
from ..tables import accounts as t


@dataclass
class Ledger:
    """Everything an account's figures are worked out from."""

    account: Account
    transactions: list[Transaction]
    lots: list[Lot]
    picks: list[LotPick]
    snapshots: list[Holding]
    anchors: list[Anchor]
    imports: list[Import]
    washes: list = field(default_factory=list)  # wash sales touching its trades (S3.8)

    def opening(self) -> balances.Opening:
        return balances.opening(self.account, self.transactions, self.anchors)

    def balance(self, day: dt.date | None = None) -> Decimal:
        day = day or dt.date.max
        return balances.balance_on(day, self.opening(), self.transactions)

    def replay(self) -> lots.Replay:
        return lots.replay(
            self.account.lotMethod,
            self.transactions,
            self.lots,
            self.picks,
            self.snapshots,
            self.washes,
        )


def load(s: Session, account: Account, raw: bool = False) -> Ledger:
    """The account's ledger; raw leaves out the wash sales, for working them out."""
    aid = account.id
    txns = s.scalars(
        select(Transaction)
        .where(Transaction.accountId == aid, Transaction.deleted == false())
        .order_by(Transaction.date, Transaction.createdAt)
    ).all()
    lot_rows = s.scalars(live(Lot, t.Lot).where(Lot.accountId == aid)).all()
    lot_ids = [x.id for x in lot_rows]
    picks = (
        s.scalars(
            select(LotPick).where(LotPick.lotId.in_(lot_ids), LotPick.deleted == false())
        ).all()
        if lot_ids
        else []
    )
    snaps = s.scalars(
        select(Holding).where(Holding.accountId == aid, Holding.deleted == false())
    ).all()
    anchors = s.scalars(
        select(Anchor)
        .where(Anchor.accountId == aid, Anchor.deleted == false())
        .order_by(Anchor.date)
    ).all()
    imports = s.scalars(
        select(Import)
        .where(Import.accountId == aid, Import.deleted == false())
        .order_by(Import.createdAt)
    ).all()
    ids_ = [x.id for x in txns]
    washes = (
        s.scalars(
            select(WashSale).where((WashSale.saleId.in_(ids_)) | (WashSale.replacementId.in_(ids_)))
        ).all()
        if ids_ and not raw
        else []
    )
    return Ledger(
        account,
        list(txns),
        list(lot_rows),
        list(picks),
        list(snaps),
        list(anchors),
        list(imports),
        list(washes),
    )


# ---------- categories ----------


def ensure_categories(s: Session) -> int:
    """Add any shipped category this database lacks, found by its key."""
    have = {c.builtIn: c for c in s.scalars(select(Category).where(Category.builtIn.is_not(None)))}
    added = 0
    for key, name, kind, tag, children in DEFAULTS:
        parent = have.get(key)
        if parent is None:
            parent = Category(id=ids.new_id("Cat"), name=name, kind=kind, taxTag=tag, builtIn=key)
            s.add(parent)
            added += 1
        for ckey, cname, ctag in children:
            if ckey not in have:
                s.add(
                    Category(
                        id=ids.new_id("Cat"),
                        name=cname,
                        kind=kind,
                        taxTag=ctag,
                        builtIn=ckey,
                        parentId=parent.id,
                    )
                )
                added += 1
    s.flush()
    return added


# ---------- instruments ----------


def instrument(
    s: Session, symbol: str | None, name: str | None, cls: str, cusip: str | None = None
) -> Instrument:
    """The instrument with this CUSIP or symbol, made if MoneyKata doesn't know it yet."""
    found = None
    if cusip:
        found = s.scalars(
            select(Instrument).where(Instrument.cusip == cusip, Instrument.deleted == false())
        ).first()
    if found is None and symbol:
        found = s.scalars(
            select(Instrument).where(
                Instrument.symbol == symbol.upper(), Instrument.deleted == false()
            )
        ).first()
    if found is not None:
        if cusip and not found.cusip:
            found.cusip = cusip
        if name and not found.name:
            found.name = name
        return found
    inst = Instrument(
        id=ids.new_id("Instr"),
        symbol=(symbol or cusip or name or "?").upper(),
        name=name,
        instrumentClass=cls,
        cusip=cusip,
    )
    s.add(inst)
    s.flush()
    return inst


# ---------- transfers (S1.7) ----------


def match_transfer(s: Session, txn: Transaction, owner_id: str) -> Transaction | None:
    """Link a transaction to its other half in another of the owner's accounts."""
    if txn.transferId or txn.amount == 0 or txn.instrumentId:
        return None
    lo, hi = transfers.window(txn)
    others = s.scalars(
        select(Transaction)
        .join(Account, Account.id == Transaction.accountId)
        .where(
            Account.ownerId == owner_id,
            Account.deleted == false(),
            Transaction.deleted == false(),
            Transaction.accountId != txn.accountId,
            Transaction.transferId.is_(None),
            Transaction.instrumentId.is_(None),
            Transaction.amount == -txn.amount,
            Transaction.date >= lo,
            Transaction.date <= hi,
        )
    ).all()
    other = transfers.best(txn, list(others))
    if other is not None:
        txn.transferId, other.transferId = other.id, txn.id
    return other


def unlink_transfer(s: Session, txn: Transaction) -> None:
    if txn.transferId:
        other = s.get(Transaction, txn.transferId)
        if other is not None and other.transferId == txn.id:
            other.transferId = None
        txn.transferId = None


# ---------- imports (S1.3.2) ----------


@dataclass
class Applied:
    importId: str
    added: int = 0
    matched: int = 0
    changed: int = 0
    transfers: int = 0
    coveredFrom: dt.date | None = None
    coveredTo: dt.date | None = None
    warnings: list[str] = field(default_factory=list)


def apply_import(
    s: Session, account: Account, user_id: str, parsed: ParsedFile, file_name: str, file_hash: str
) -> Applied:
    """Add what is new: rows are matched by the file's transaction id (an OFX FITID), or by
    date, amount and payee. A re-imported file adds nothing; an amount that changed between
    imports is updated and kept for the reconciliation's suspects (S1.11.3)."""
    imp = Import(
        id=ids.new_id("Imprt"),
        accountId=account.id,
        userId=user_id,
        format=parsed.format,
        fileName=file_name[:200],
        fileHash=file_hash,
        coveredFrom=parsed.coveredFrom,
        coveredTo=parsed.coveredTo,
    )
    s.add(imp)
    s.flush()
    result = Applied(imp.id, coveredFrom=parsed.coveredFrom, coveredTo=parsed.coveredTo)
    instruments: dict[str, Instrument] = {}
    for key, sec in parsed.securities.items():
        instruments[key] = instrument(s, sec.symbol, sec.name, sec.instrumentClass, sec.cusip)

    existing = s.scalars(
        select(Transaction).where(
            Transaction.accountId == account.id, Transaction.deleted == false()
        )
    ).all()
    by_fit = {x.fitId: x for x in existing if x.fitId}
    loose: dict[tuple, list[Transaction]] = {}
    for x in existing:
        if not x.fitId:
            loose.setdefault(_loose_key(x.date, x.amount, x.payeeRaw), []).append(x)

    added: list[Transaction] = []
    for row in parsed.rows:
        inst = instruments.get(row.security) if row.security else None
        found = by_fit.get(row.fitId) if row.fitId else None
        if found is None and not row.fitId:
            bucket = loose.get(_loose_key(row.date, row.amount, row.payee))
            found = bucket.pop(0) if bucket else None
        if found is not None:
            if found.amount != row.amount:
                found.amountWas, found.amount = found.amount, row.amount
                result.changed += 1
            else:
                result.matched += 1
            if row.runningBalance is not None:
                found.runningBalance = row.runningBalance
            continue
        txn = Transaction(
            id=ids.new_id("Txn"),
            accountId=account.id,
            date=row.date,
            kind=row.kind,
            amount=row.amount,
            payee=_payee(row.payee),
            payeeRaw=row.payee,
            memo=row.memo,
            instrumentId=inst.id if inst else None,
            quantity=row.quantity,
            price=row.price,
            fees=row.fees,
            dividendType=row.dividendType,
            splitRatio=row.splitRatio,
            importId=imp.id,
            fitId=row.fitId,
            runningBalance=row.runningBalance,
            createdById=user_id,
            contributionYear=row.date.year
            if row.kind == "deposit" and _retirement(account)
            else None,
        )
        s.add(txn)
        s.flush()
        if inst and row.kind in ("buy", "reinvest", "transfer-in") and row.quantity:
            s.add(
                Lot(
                    id=ids.new_id("Lot"),
                    accountId=account.id,
                    instrumentId=inst.id,
                    transactionId=txn.id,
                    acquiredOn=row.date,
                    quantity=row.quantity,
                    costBasis=-row.amount if row.kind != "transfer-in" else None,
                    basisMissing=row.kind == "transfer-in",
                )
            )
        if row.fitId:
            by_fit[row.fitId] = txn
        added.append(txn)
    result.added = len(added)
    s.flush()

    # A balance the file reports: an OFX file's, or a statement's opening and closing.
    source = "statement" if parsed.format == "statement" else "ofx"
    for day, balance in parsed.balances:
        if (
            day
            and not s.scalars(
                select(Anchor).where(
                    Anchor.accountId == account.id,
                    Anchor.date == day,
                    Anchor.source == source,
                    Anchor.deleted == false(),
                )
            ).first()
        ):
            s.add(
                Anchor(
                    id=ids.new_id("Anchr"),
                    accountId=account.id,
                    date=day,
                    balance=balance,
                    source=source,
                    importId=imp.id,
                )
            )
    for pos in parsed.positions:
        inst = instruments.get(pos.security)
        if inst is None:
            result.warnings.append("a position names a security the file doesn't describe")
            continue
        if not s.scalars(
            select(Holding).where(
                Holding.accountId == account.id,
                Holding.instrumentId == inst.id,
                Holding.asOf == pos.asOf,
                Holding.deleted == false(),
            )
        ).first():
            s.add(
                Holding(
                    id=ids.new_id("Hold"),
                    accountId=account.id,
                    instrumentId=inst.id,
                    asOf=pos.asOf,
                    quantity=pos.quantity,
                    marketValue=pos.marketValue,
                    importId=imp.id,
                )
            )
    for txn in added:
        if match_transfer(s, txn, account.ownerId):
            result.transfers += 1
    imp.added, imp.matched, imp.changed = result.added, result.matched, result.changed
    activity.record(
        s,
        "account.imported",
        actor=user_id,
        subject_kind="account",
        subject_id=account.id,
        owner=account.ownerId,
        detail={
            "added": result.added,
            "matched": result.matched,
            "changed": result.changed,
            "format": parsed.format,
        },
    )
    if any(r.instrumentId for r in txns_made(s, imp.id)):
        from ... import washes

        s.flush()
        washes.recompute(s, account.ownerId)
    return result


def txns_made(s: Session, import_id: str) -> list[Transaction]:
    return list(
        s.scalars(
            select(Transaction).where(
                Transaction.importId == import_id, Transaction.deleted == false()
            )
        )
    )


def _loose_key(day: dt.date, amount: Decimal, payee: str | None) -> tuple:
    return (day, amount, (payee or "").strip().lower())


def _payee(raw: str | None) -> str | None:
    return " ".join(raw.split()) if raw else None


def _retirement(account: Account) -> bool:
    from ...ledger.types import retirement

    return retirement(account.type)


def latest_activity(s: Session, account_ids: list[str]) -> dict[str, dt.datetime]:
    """When each account was last updated: its newest import or transaction."""
    if not account_ids:
        return {}
    rows = s.execute(
        select(Transaction.accountId, func.max(Transaction.updatedAt))
        .where(Transaction.accountId.in_(account_ids), Transaction.deleted == false())
        .group_by(Transaction.accountId)
    ).all()
    return dict(rows)


def search_instruments(s: Session, query: str, limit: int = 20) -> list[Instrument]:
    q = f"%{query.strip().upper()}%"
    return list(
        s.scalars(
            select(Instrument)
            .where(
                Instrument.deleted == false(),
                or_(Instrument.symbol.like(q), func.upper(Instrument.name).like(q)),
            )
            .order_by(Instrument.symbol)
            .limit(limit)
        )
    )
