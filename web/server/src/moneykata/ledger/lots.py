"""Lots and gains (requirements §5.2, §5.3): replaying an account's transactions consumes its
lots by the lot method in force at each sale. A holding snapshot from a broker's file stands
in for history that is missing, marked as such (§3.2)."""

import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal

ZERO = Decimal(0)
CENT = Decimal("0.01")


@dataclass
class OpenLot:
    lotId: str | None
    instrumentId: str
    acquiredOn: dt.date
    quantity: Decimal
    basis: Decimal | None  # what remains of the cost basis; None while it is missing
    standIn: bool = False  # made from a holding snapshot, not a transaction

    @property
    def basisMissing(self) -> bool:
        return self.basis is None

    @property
    def unitBasis(self) -> Decimal | None:
        return None if self.basis is None or not self.quantity else self.basis / self.quantity


@dataclass
class Disposal:
    saleId: str | None
    lotId: str | None
    instrumentId: str
    acquiredOn: dt.date
    soldOn: dt.date
    quantity: Decimal
    proceeds: Decimal
    basis: Decimal | None
    method: str

    @property
    def gain(self) -> Decimal | None:
        return None if self.basis is None else (self.proceeds - self.basis).quantize(CENT)

    @property
    def longTerm(self) -> bool:
        """Held more than a year (§6.1)."""
        try:
            anniversary = self.acquiredOn.replace(year=self.acquiredOn.year + 1)
        except ValueError:  # 29 February
            anniversary = self.acquiredOn.replace(year=self.acquiredOn.year + 1, day=28)
        return self.soldOn > anniversary


@dataclass
class Problem:
    """Missing or doubtful data (§11.4): a sale without a lot, a snapshot that explains a gap."""

    kind: str
    instrumentId: str
    date: dt.date
    transactionId: str | None
    quantity: Decimal


@dataclass
class Replay:
    open: list[OpenLot] = field(default_factory=list)
    disposals: list[Disposal] = field(default_factory=list)
    problems: list[Problem] = field(default_factory=list)

    def quantity(self, instrument_id: str) -> Decimal:
        return sum((lot.quantity for lot in self.open if lot.instrumentId == instrument_id), ZERO)

    def positions(self) -> dict[str, Decimal]:
        out: dict[str, Decimal] = {}
        for lot in self.open:
            out[lot.instrumentId] = out.get(lot.instrumentId, ZERO) + lot.quantity
        return {k: v for k, v in out.items() if v}


def _order(method: str, lots: list[OpenLot]) -> list[OpenLot]:
    if method == "lifo":
        return sorted(lots, key=lambda x: x.acquiredOn, reverse=True)
    if method == "hifo":
        return sorted(lots, key=lambda x: (x.unitBasis is None, -(x.unitBasis or ZERO)))
    return sorted(lots, key=lambda x: x.acquiredOn)


def _take(lot: OpenLot, qty: Decimal) -> Decimal | None:
    """Take qty from a lot; returns the basis that goes with it."""
    if lot.basis is None:
        lot.quantity -= qty
        return None
    if qty == lot.quantity:
        basis, lot.basis = lot.basis, ZERO
    else:
        basis = (lot.basis * qty / lot.quantity).quantize(CENT)
        lot.basis -= basis
    lot.quantity -= qty
    return basis


def replay(
    account_method: str, transactions: list, lots: list, picks: list, snapshots: list
) -> Replay:
    """Transactions, lots (acquisitions), specific-identification picks and holding
    snapshots of one account, as entities; returns the open lots, disposals and problems."""
    lots_by_txn: dict[str, list] = {}
    for lot in lots:
        if lot.transactionId:
            lots_by_txn.setdefault(lot.transactionId, []).append(lot)
    picks_by_sale: dict[str, list] = {}
    for p in picks:
        picks_by_sale.setdefault(p.saleId, []).append(p)

    events: list[tuple] = []
    for t in transactions:
        events.append((t.date, 0, t.createdAt, t.id, "txn", t))
    for lot in lots:
        if not lot.transactionId:
            events.append((lot.acquiredOn, 0, lot.createdAt, lot.id, "lot", lot))
    for h in snapshots:
        events.append((h.asOf, 1, h.createdAt, h.id, "snapshot", h))  # at the day's end
    events.sort(key=lambda e: e[:4])

    out = Replay()
    for _, _, _, _, what, obj in events:
        if what == "lot":
            out.open.append(
                OpenLot(
                    obj.id,
                    obj.instrumentId,
                    obj.acquiredOn,
                    obj.quantity,
                    None if obj.basisMissing else obj.costBasis,
                )
            )
        elif what == "snapshot":
            _snapshot(out, obj)
        else:
            _transaction(
                out, obj, account_method, lots_by_txn.get(obj.id, []), picks_by_sale.get(obj.id, [])
            )
    out.open = [lot for lot in out.open if lot.quantity]
    return out


def _transaction(out: Replay, t, account_method: str, made: list, picks: list) -> None:
    if not t.instrumentId:
        return
    if t.kind in ("buy", "reinvest", "transfer-in"):
        if made:
            for lot in made:
                out.open.append(
                    OpenLot(
                        lot.id,
                        lot.instrumentId,
                        lot.acquiredOn,
                        lot.quantity,
                        None if lot.basisMissing else lot.costBasis,
                    )
                )
        elif t.quantity:
            basis = -t.amount if t.kind != "transfer-in" and t.amount else None
            out.open.append(OpenLot(None, t.instrumentId, t.date, t.quantity, basis))
    elif t.kind in ("sell", "transfer-out"):
        qty = abs(t.quantity or ZERO)
        if not qty:
            return
        method = t.lotMethod or account_method
        proceeds = t.amount if t.kind == "sell" else ZERO
        _consume(out, t, qty, method, proceeds, picks, realize=t.kind == "sell")
    elif t.kind == "split" and t.splitRatio:
        for lot in out.open:
            if lot.instrumentId == t.instrumentId:
                lot.quantity *= t.splitRatio
    elif t.kind == "return-of-capital":
        held = [lot for lot in out.open if lot.instrumentId == t.instrumentId and lot.basis]
        total = sum((lot.quantity for lot in held), ZERO)
        for lot in held:
            cut = (t.amount * lot.quantity / total).quantize(CENT) if total else ZERO
            lot.basis = max(ZERO, lot.basis - cut)


def _consume(
    out: Replay, t, qty: Decimal, method: str, proceeds: Decimal, picks: list, realize: bool
) -> None:
    """Take a sale's quantity from the open lots: the picked lots for specific
    identification, else in the method's order; average cost pools the basis (§5.3)."""
    held = [lot for lot in out.open if lot.instrumentId == t.instrumentId and lot.quantity > 0]
    total, left = qty, qty
    plan: list[tuple[OpenLot, Decimal]] = []
    if method == "specific" and picks:
        by_id = {lot.lotId: lot for lot in held}
        for p in picks:
            lot = by_id.get(p.lotId)
            take = min(p.quantity, lot.quantity, left) if lot else ZERO
            if take > 0:
                plan.append((lot, take))
                left -= take
    order = method if method in ("fifo", "lifo", "hifo") else "fifo"
    for lot in _order(order, held):
        if left <= 0:
            break
        room = lot.quantity - sum((q for p, q in plan if p is lot), ZERO)
        take = min(left, room)
        if take > 0:
            plan.append((lot, take))
            left -= take
    avg = None
    if method == "average" and held and all(lot.basis is not None for lot in held):
        pool = sum((lot.quantity for lot in held), ZERO)
        avg = sum((lot.basis for lot in held), ZERO) / pool if pool else None
    used = (
        method
        if method in ("fifo", "lifo", "hifo", "average")
        else ("specific" if picks else "fifo")
    )
    allotted = ZERO
    for i, (lot, take) in enumerate(plan):
        last = i == len(plan) - 1 and left <= 0
        share = proceeds - allotted if last else (proceeds * take / total).quantize(CENT)
        allotted += share
        basis = _take(lot, take)
        if avg is not None:
            basis = (avg * take).quantize(CENT)
            lot.basis = (avg * lot.quantity).quantize(CENT)
        if realize:
            out.disposals.append(
                Disposal(
                    t.id,
                    lot.lotId,
                    t.instrumentId,
                    lot.acquiredOn,
                    t.date,
                    take,
                    share,
                    basis,
                    used,
                )
            )
    if left > 0:
        _unmatched(out, t, left, proceeds - allotted, realize, used)


def _unmatched(out: Replay, t, qty: Decimal, proceeds: Decimal, realize: bool, method: str) -> None:
    """More sold than held: a sale without a matching lot (§11.4)."""
    out.problems.append(Problem("sale-without-lot", t.instrumentId, t.date, t.id, qty))
    if realize:
        out.disposals.append(
            Disposal(
                t.id,
                None,
                t.instrumentId,
                t.date,
                t.date,
                qty,
                proceeds.quantize(CENT),
                None,
                method,
            )
        )


def _snapshot(out: Replay, h) -> None:
    """A broker's file says how much is held on a day; what the transactions can't explain
    becomes a stand-in lot with its basis missing, or is taken away."""
    have = out.quantity(h.instrumentId)
    delta = h.quantity - have
    if delta > 0:
        out.open.append(OpenLot(None, h.instrumentId, h.asOf, delta, None, standIn=True))
        out.problems.append(Problem("history-missing", h.instrumentId, h.asOf, None, delta))
    elif delta < 0:
        qty = -delta
        for lot in _order("fifo", [x for x in out.open if x.instrumentId == h.instrumentId]):
            if qty <= 0:
                break
            take = min(qty, lot.quantity)
            _take(lot, take)
            qty -= take
        out.problems.append(Problem("history-missing", h.instrumentId, h.asOf, None, delta))
