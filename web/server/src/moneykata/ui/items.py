"""Physical assets (requirements S1.10): a physical-asset account's items, each valued at spot,
from dated valuations or by depreciation; a property's improvements; photos and documents kept
as receipts; selling an item; and precious metals summarised by metal."""

import datetime as dt
from decimal import Decimal

from fastapi import APIRouter, Depends, Request
from sqlalchemy import false, select

from .. import access, activity, assets, clock, ids, loans, receipts, valuation
from ..errors import FieldError, Problem, refuse
from ..store.entities.accounts import Account, Loan
from ..store.entities.assets import Improvement, Item, ItemValuation
from .conventions import (
    Deleted,
    ExactRoute,
    Gone,
    Model,
    Money,
    Quantity,
    Ratio,
    check,
    gone,
    if_match,
)
from .deps import Caller, caller, server
from .receipts import ReceiptRow
from .receipts import row as receipt_row

router = APIRouter(prefix="/ui/api", route_class=ExactRoute, tags=["items"])

HOW = ("bought", "gift", "inherited")
VALUATIONS = ("spot", "valuations", "depreciation")
SOURCES = ("appraisal", "sale", "guide", "estimate")


class ItemIn(Model):
    name: str
    category: str | None = None
    description: str | None = None
    acquiredOn: dt.date
    acquiredHow: str = "bought"
    costBasis: Money
    quantity: Quantity = Decimal(1)
    location: str | None = None
    serial: str | None = None
    condition: str | None = None
    insuredValue: Money | None = None
    policy: str | None = None
    notes: str | None = None
    valuation: str = "valuations"
    metal: str | None = None
    unitWeight: Quantity | None = None
    weightUnit: str | None = None
    purity: str | None = None  # ".9999", ".925", "22k"
    sellPremium: Money = Decimal(0)
    depreciationRate: Money | None = None
    address: str | None = None
    closingCosts: Money | None = None
    primaryResidence: bool = False
    personalUse: bool = False


class ValuationOut(Model):
    id: str
    date: dt.date
    value: Money
    source: str
    note: str | None
    version: int


class ImprovementOut(Model):
    id: str
    date: dt.date
    description: str
    amount: Money
    version: int


class SecuredLoan(Model):
    accountId: str
    name: str
    owed: Money


class Sale(Model):
    soldOn: dt.date
    proceeds: Money
    fees: Money
    gain: Money
    collectable: bool  # taxed at the collectables rate (S1.10.5)
    deductible: bool  # a loss on personal-use property is not (S8.13)


class ItemRow(Model):
    id: str
    accountId: str
    name: str
    category: str | None
    acquiredOn: dt.date
    acquiredHow: str
    quantity: Quantity
    valuation: str
    metal: str | None
    fineOunces: Quantity | None
    basis: Money
    value: Money
    gain: Money
    years: Ratio  # how long it has been held
    latest: ValuationOut | None
    stale: bool
    sale: Sale | None
    loans: list[SecuredLoan]
    equity: Money | None
    version: int


class ItemDetail(ItemRow):
    description: str | None
    costBasis: Money
    location: str | None
    serial: str | None
    condition: str | None
    insuredValue: Money | None
    policy: str | None
    notes: str | None
    unitWeight: Quantity | None
    weightUnit: str | None
    purity: Quantity | None
    sellPremium: Money
    depreciationRate: Money | None
    address: str | None
    closingCosts: Money | None
    primaryResidence: bool
    personalUse: bool
    spot: Money | None
    spotAsOf: dt.date | None
    valuations: list[ValuationOut]
    improvements: list[ImprovementOut]
    documents: list[ReceiptRow]
    history: list[tuple[dt.date, Money]]
    canWrite: bool


class MetalOut(Model):
    metal: str
    ounces: Quantity
    cost: Money
    averageCost: Money | None
    spot: Money | None
    spotAsOf: dt.date | None
    value: Money
    gain: Money


class ItemsView(Model):
    items: list[ItemRow]
    metals: list[MetalOut]
    value: Money
    basis: Money
    gain: Money
    canWrite: bool


class ValuationIn(Model):
    date: dt.date
    value: Money
    source: str = "estimate"
    note: str | None = None


class ImprovementIn(Model):
    date: dt.date
    description: str
    amount: Money


class SaleIn(Model):
    soldOn: dt.date
    proceeds: Money
    fees: Money = Decimal(0)


class DocumentIn(Model):
    receiptId: str


def _account(s, c: Caller, account_id: str, need: str = "read") -> tuple[Account, str]:
    a, lvl = access.account(s, c.id, account_id, need)
    if not assets.is_physical(a.type):
        raise Problem(409, "not-physical", "This account doesn't hold items.")
    return a, lvl


def _item(s, c: Caller, item_id: str, need: str = "read") -> tuple[Item, Account, str]:
    it = s.get(Item, item_id)
    if it is None or it.deleted:
        raise Problem(404, "not-found", "No such item.")
    a, lvl = _account(s, c, it.accountId, need)
    return it, a, lvl


def _secured(s, item_ids: list[str], day: dt.date) -> dict[str, list[SecuredLoan]]:
    """The live loans secured by each item, with what is owed on them."""
    out: dict[str, list[SecuredLoan]] = {i: [] for i in item_ids}
    if not item_ids:
        return out
    for row in s.scalars(
        select(Loan).where(Loan.securedById.in_(item_ids), Loan.deleted == false())
    ):
        a = s.get(Account, row.accountId)
        if a is None or a.deleted:
            continue
        owed = -loans.value(s, a, day)
        out[row.securedById].append(SecuredLoan(accountId=a.id, name=a.name, owed=owed))
    return out


def _valuation_out(v: ItemValuation) -> ValuationOut:
    return ValuationOut(
        id=v.id, date=v.date, value=v.value, source=v.source, note=v.note, version=v.version
    )


def _sale(a: Account, it: Item, d: assets.Detail) -> Sale | None:
    g = assets.gain(it, d)
    if g is None:
        return None
    return Sale(
        soldOn=it.soldOn,
        proceeds=it.proceeds,
        fees=it.saleFees or Decimal(0),
        gain=g,
        collectable=assets.is_collectable(a.type, it),
        deductible=not (g < 0 and it.personalUse),
    )


def _row(a: Account, it: Item, d: assets.Detail, spot, secured, today) -> ItemRow:
    value = assets.value_on(it, d, today, spot)
    basis = assets.basis(it, d)
    latest = assets.latest_valuation(d, today)
    owed = sum((x.owed for x in secured), Decimal(0))
    end = it.soldOn or today
    return ItemRow(
        id=it.id,
        accountId=a.id,
        name=it.name,
        category=it.category,
        acquiredOn=it.acquiredOn,
        acquiredHow=it.acquiredHow,
        quantity=it.quantity,
        valuation=it.valuation,
        metal=it.metal,
        fineOunces=assets.fine_ounces(it).quantize(Decimal("0.0001"))
        if it.valuation == "spot"
        else None,
        basis=basis,
        value=value,
        gain=(value - basis) if it.soldOn is None else (assets.gain(it, d) or Decimal(0)),
        years=round((end - it.acquiredOn).days / 365.25, 1),
        latest=_valuation_out(latest) if latest else None,
        stale=assets.is_stale(it, d, today),
        sale=_sale(a, it, d),
        loans=secured,
        equity=(value - owed) if secured and it.soldOn is None else None,
        version=it.version,
    )


def view(s, a: Account, lvl: str) -> ItemsView:
    today = clock.today()
    items = assets.items_of(s, a)
    ds = assets.details(s, items)
    sp = assets.spots(s, items, today)
    sec = _secured(s, [i.id for i in items], today)
    rows = [
        _row(a, i, ds[i.id], sp[i.metal].price if i.metal in sp else None, sec[i.id], today)
        for i in items
    ]
    held = [r for r in rows if r.sale is None]
    return ItemsView(
        items=rows,
        metals=[MetalOut(**m.__dict__) for m in assets.metals(s, items, today)],
        value=sum((r.value for r in held), Decimal(0)),
        basis=sum((r.basis for r in held), Decimal(0)),
        gain=sum((r.gain for r in held), Decimal(0)),
        canWrite=lvl in ("owner", "write"),
    )


def detail(s, c: Caller, it: Item, a: Account, lvl: str) -> ItemDetail:
    today = clock.today()
    d = assets.details(s, [it])[it.id]
    sp = assets.spots(s, [it], today).get(it.metal or "")
    sec = _secured(s, [it.id], today)[it.id]
    base = _row(a, it, d, sp.price if sp else None, sec, today)
    # Its value at each month's end since it was acquired, for its history.
    first = it.acquiredOn
    history = []
    month = dt.date(first.year, first.month, 1)
    pts = []
    inst = assets.find_metal(s, it.metal) if it.valuation == "spot" and it.metal else None
    if inst is not None:
        pts = valuation.price_points(s, [inst.id], first, today).get(inst.id, [])
    end = it.soldOn or today
    k = 0
    current = None
    while month <= end:
        nxt = dt.date(month.year + month.month // 12, month.month % 12 + 1, 1)
        day = min(nxt - dt.timedelta(days=1), end)
        while k < len(pts) and pts[k][0] <= day:
            current = pts[k][1]
            k += 1
        history.append((day, assets.value_on(it, d, max(day, first), current)))
        month = nxt
    return ItemDetail(
        **base.model_dump(),
        description=it.description,
        costBasis=it.costBasis,
        location=it.location,
        serial=it.serial,
        condition=it.condition,
        insuredValue=it.insuredValue,
        policy=it.policy,
        notes=it.notes,
        unitWeight=it.unitWeight,
        weightUnit=it.weightUnit,
        purity=it.purity,
        sellPremium=it.sellPremium,
        depreciationRate=it.depreciationRate,
        address=it.address,
        closingCosts=it.closingCosts,
        primaryResidence=it.primaryResidence,
        personalUse=it.personalUse,
        spot=sp.price if sp else None,
        spotAsOf=sp.asOf if sp else None,
        valuations=[_valuation_out(v) for v in reversed(d.valuations)],
        improvements=[
            ImprovementOut(
                id=m.id,
                date=m.date,
                description=m.description,
                amount=m.amount,
                version=m.version,
            )
            for m in reversed(d.improvements)
        ],
        documents=[
            receipt_row(s, r, receipts.level(s, c.id, r) or "read")
            for r in receipts.of_item(s, it.id)
        ],
        history=history,
        canWrite=lvl in ("owner", "write"),
    )


def _clean(v: str | None) -> str | None:
    v = (v or "").strip()
    return v or None


def _values(body: ItemIn, account_type: str) -> dict:
    """The item's columns from the form, or every refusal at once."""
    e: list[FieldError] = []
    name = body.name.strip()
    if not name or len(name) > 120:
        e.append(FieldError("name", "name-invalid", "A name, up to 120 characters."))
    if body.acquiredHow not in HOW:
        e.append(FieldError("acquiredHow", "how-invalid", "Bought, a gift or inherited."))
    if body.acquiredOn > clock.today():
        e.append(FieldError("acquiredOn", "date-ahead", "Not after today."))
    if body.costBasis < 0:
        e.append(FieldError("costBasis", "amount-invalid", "Zero or more."))
    if body.quantity <= 0:
        e.append(FieldError("quantity", "quantity-invalid", "More than zero."))
    if body.valuation not in VALUATIONS:
        e.append(FieldError("valuation", "valuation-invalid", "Spot, valuations or depreciation."))
    for f in ("insuredValue", "closingCosts"):
        v = getattr(body, f)
        if v is not None and v < 0:
            e.append(FieldError(f, "amount-invalid", "Zero or more."))
    purity = None
    if body.valuation == "spot":
        if body.metal not in assets.METAL_SYMBOLS:
            e.append(FieldError("metal", "metal-invalid", "Gold, silver, platinum or palladium."))
        if body.unitWeight is None or body.unitWeight <= 0:
            e.append(FieldError("unitWeight", "weight-invalid", "The weight of one unit."))
        if body.weightUnit not in assets.OUNCES:
            e.append(FieldError("weightUnit", "unit-invalid", "Troy ounces, grams or kilograms."))
        try:
            purity = assets.parse_purity(body.purity or "")
        except ValueError:
            e.append(FieldError("purity", "purity-invalid", "Such as .9999, .925 or 22k."))
        if not -50 <= body.sellPremium <= 100:
            e.append(FieldError("sellPremium", "premium-invalid", "Between −50% and 100%."))
    if body.valuation == "depreciation" and not (
        body.depreciationRate is not None and 0 < body.depreciationRate < 100
    ):
        e.append(FieldError("depreciationRate", "rate-invalid", "A yearly percentage."))
    if e:
        raise Problem(422, e[0].code, e[0].message, e)
    spot = body.valuation == "spot"
    return {
        "name": name,
        "category": _clean(body.category),
        "description": _clean(body.description),
        "acquiredOn": body.acquiredOn,
        "acquiredHow": body.acquiredHow,
        "costBasis": body.costBasis,
        "quantity": body.quantity,
        "location": _clean(body.location),
        "serial": _clean(body.serial),
        "condition": _clean(body.condition),
        "insuredValue": body.insuredValue,
        "policy": _clean(body.policy),
        "notes": body.notes or None,
        "valuation": body.valuation,
        "metal": body.metal if spot else None,
        "unitWeight": body.unitWeight if spot else None,
        "weightUnit": body.weightUnit if spot else None,
        "purity": purity,
        "sellPremium": body.sellPremium if spot else Decimal(0),
        "depreciationRate": body.depreciationRate if body.valuation == "depreciation" else None,
        "address": _clean(body.address) if account_type == "real-estate" else None,
        "closingCosts": body.closingCosts if account_type == "real-estate" else None,
        "primaryResidence": body.primaryResidence and account_type == "real-estate",
        "personalUse": body.personalUse,
    }


def _record(s, kind: str, c: Caller, a: Account) -> None:
    activity.record(s, kind, actor=c.id, subject_kind="account", subject_id=a.id, owner=a.ownerId)


@router.get("/accounts/{account_id}/items", response_model=ItemsView)
def list_items(account_id: str, request: Request, c: Caller = Depends(caller)):
    with server(request).db.read() as s:
        a, lvl = _account(s, c, account_id)
        return view(s, a, lvl)


@router.post("/accounts/{account_id}/items", response_model=ItemDetail, status_code=201)
def add_item(account_id: str, body: ItemIn, request: Request, c: Caller = Depends(caller)):
    with server(request).db.tx() as s:
        a, lvl = _account(s, c, account_id, "write")
        values = _values(body, a.type)
        it = Item(id=ids.new_id("Item"), accountId=a.id, createdById=c.id, **values)
        s.add(it)
        if it.metal:
            assets.metal_instrument(s, it.metal)  # so the refresh prices its spot
        s.flush()
        _record(s, "item.added", c, a)
        return detail(s, c, it, a, lvl)


@router.get("/items/{item_id}", response_model=ItemDetail)
def get_item(item_id: str, request: Request, c: Caller = Depends(caller)):
    with server(request).db.read() as s:
        it, a, lvl = _item(s, c, item_id)
        return detail(s, c, it, a, lvl)


@router.patch("/items/{item_id}", response_model=ItemDetail)
def change_item(
    item_id: str,
    body: ItemIn,
    request: Request,
    c: Caller = Depends(caller),
    version: int = Depends(if_match),
):
    with server(request).db.tx() as s:
        it, a, lvl = _item(s, c, item_id, "write")
        check(it, version, lambda: detail(s, c, it, a, lvl))
        for k, v in _values(body, a.type).items():
            setattr(it, k, v)
        if it.metal:
            assets.metal_instrument(s, it.metal)
        it.updatedAt = clock.now()
        s.flush()
        _record(s, "item.changed", c, a)
        return detail(s, c, it, a, lvl)


@router.delete("/items/{item_id}", response_model=Deleted[None])
def delete_item(
    item_id: str, request: Request, c: Caller = Depends(caller), version: int = Depends(if_match)
):
    with server(request).db.tx() as s:
        it, a, lvl = _item(s, c, item_id, "write")
        check(it, version, lambda: detail(s, c, it, a, lvl))
        it.mark_deleted(c.id)
        _record(s, "item.deleted", c, a)
        s.flush()
        return Deleted[None](deleted=gone(it))


@router.post("/items/{item_id}/valuations", response_model=ItemDetail, status_code=201)
def add_valuation(item_id: str, body: ValuationIn, request: Request, c: Caller = Depends(caller)):
    if body.value < 0:
        raise refuse("value", "amount-invalid", "Zero or more.")
    if body.source not in SOURCES:
        raise refuse("source", "source-invalid", "Appraisal, sale, guide or estimate.")
    if body.date > clock.today():
        raise refuse("date", "date-ahead", "Not after today.")
    with server(request).db.tx() as s:
        it, a, lvl = _item(s, c, item_id, "write")
        s.add(
            ItemValuation(
                id=ids.new_id("Valtn"),
                itemId=it.id,
                date=body.date,
                value=body.value,
                source=body.source,
                note=_clean(body.note),
                createdById=c.id,
            )
        )
        s.flush()
        return detail(s, c, it, a, lvl)


@router.delete("/items/{item_id}/valuations/{valuation_id}", response_model=Deleted[ItemDetail])
def delete_valuation(
    item_id: str,
    valuation_id: str,
    request: Request,
    c: Caller = Depends(caller),
    version: int = Depends(if_match),
):
    with server(request).db.tx() as s:
        it, a, lvl = _item(s, c, item_id, "write")
        v = s.get(ItemValuation, valuation_id)
        if v is None or v.deleted or v.itemId != it.id:
            raise Problem(404, "not-found", "No such valuation.")
        check(v, version, lambda: detail(s, c, it, a, lvl))
        v.mark_deleted(c.id)
        s.flush()
        return Deleted[ItemDetail](deleted=gone(v), parent=detail(s, c, it, a, lvl))


@router.post("/items/{item_id}/improvements", response_model=ItemDetail, status_code=201)
def add_improvement(
    item_id: str, body: ImprovementIn, request: Request, c: Caller = Depends(caller)
):
    if not body.description.strip():
        raise refuse("description", "description-missing", "What was done.")
    if body.amount <= 0:
        raise refuse("amount", "amount-invalid", "More than zero.")
    with server(request).db.tx() as s:
        it, a, lvl = _item(s, c, item_id, "write")
        s.add(
            Improvement(
                id=ids.new_id("Imprv"),
                itemId=it.id,
                date=body.date,
                description=body.description.strip(),
                amount=body.amount,
                createdById=c.id,
            )
        )
        s.flush()
        return detail(s, c, it, a, lvl)


@router.delete("/items/{item_id}/improvements/{improvement_id}", response_model=Deleted[ItemDetail])
def delete_improvement(
    item_id: str,
    improvement_id: str,
    request: Request,
    c: Caller = Depends(caller),
    version: int = Depends(if_match),
):
    with server(request).db.tx() as s:
        it, a, lvl = _item(s, c, item_id, "write")
        m = s.get(Improvement, improvement_id)
        if m is None or m.deleted or m.itemId != it.id:
            raise Problem(404, "not-found", "No such improvement.")
        check(m, version, lambda: detail(s, c, it, a, lvl))
        m.mark_deleted(c.id)
        s.flush()
        return Deleted[ItemDetail](deleted=gone(m), parent=detail(s, c, it, a, lvl))


@router.put("/items/{item_id}/sale", response_model=ItemDetail)
def sell(
    item_id: str,
    body: SaleIn,
    request: Request,
    c: Caller = Depends(caller),
    version: int = Depends(if_match),
):
    """Records the sale: the gain or loss is realized, and the item leaves the account's value
    from that day (S1.10.5). The sale is part of the item, so it is made against its version."""
    if body.proceeds < 0 or body.fees < 0:
        raise refuse("proceeds" if body.proceeds < 0 else "fees", "amount-invalid", "Zero or more.")
    with server(request).db.tx() as s:
        it, a, lvl = _item(s, c, item_id, "write")
        check(it, version, lambda: detail(s, c, it, a, lvl))
        if body.soldOn < it.acquiredOn:
            raise refuse("soldOn", "sold-before-bought", "On or after the day it was acquired.")
        if body.soldOn > clock.today():
            raise refuse("soldOn", "date-ahead", "Not after today.")
        it.soldOn, it.proceeds, it.saleFees = body.soldOn, body.proceeds, body.fees
        it.updatedAt = clock.now()
        s.flush()
        _record(s, "item.sold", c, a)
        return detail(s, c, it, a, lvl)


@router.delete("/items/{item_id}/sale", response_model=Deleted[ItemDetail])
def unsell(
    item_id: str, request: Request, c: Caller = Depends(caller), version: int = Depends(if_match)
):
    with server(request).db.tx() as s:
        it, a, lvl = _item(s, c, item_id, "write")
        check(it, version, lambda: detail(s, c, it, a, lvl))
        it.soldOn = it.proceeds = it.saleFees = None
        it.updatedAt = clock.now()
        s.flush()
        return Deleted[ItemDetail](
            deleted=Gone(id=f"{it.id}/sale", deletedAt=clock.now()), parent=detail(s, c, it, a, lvl)
        )


@router.post("/items/{item_id}/documents", response_model=ItemDetail)
def attach_document(item_id: str, body: DocumentIn, request: Request, c: Caller = Depends(caller)):
    """A photo or document (an uploaded receipt) kept with the item: a purchase receipt, an
    appraisal, a certificate, a title."""
    with server(request).db.tx() as s:
        it, a, lvl = _item(s, c, item_id, "write")
        r = receipts.to_attach(s, c.id, body.receiptId)
        receipts.attach_item(s, c.id, r, it)
        return detail(s, c, it, a, lvl)


@router.delete("/items/{item_id}/documents/{receipt_id}", response_model=Deleted[ItemDetail])
def detach_document(item_id: str, receipt_id: str, request: Request, c: Caller = Depends(caller)):
    """A receipt's link to the item: a pair with no version of its own (S13.8.6)."""
    with server(request).db.tx() as s:
        it, a, lvl = _item(s, c, item_id, "write")
        r, _ = receipts.get(s, c.id, receipt_id)
        receipts.detach_item(s, c.id, r, it)
        s.flush()
        return Deleted[ItemDetail](
            deleted=Gone(id=f"{r.id}/{it.id}", deletedAt=clock.now()),
            parent=detail(s, c, it, a, lvl),
        )


class Securable(Model):
    id: str
    name: str
    accountId: str
    accountName: str


@router.get("/items", response_model=list[Securable])
def securable(request: Request, c: Caller = Depends(caller)):
    """Items a loan can be secured by: unsold property, vehicles and other assets the caller
    can see (S1.9.5)."""
    with server(request).db.read() as s:
        accts = {
            a.id: a
            for a, _ in access.visible_accounts(s, c.id)
            if a.type in ("real-estate", "vehicle", "other-asset")
        }
        if not accts:
            return []
        rows = s.scalars(
            select(Item)
            .where(Item.accountId.in_(list(accts)), Item.deleted == false(), Item.soldOn.is_(None))
            .order_by(Item.name)
        )
        return [
            Securable(
                id=i.id, name=i.name, accountId=i.accountId, accountName=accts[i.accountId].name
            )
            for i in rows
        ]
