"""Gifts (requirements S7.7, S7.8): people and their occasions, gifts from idea to given and
those received, the occasions coming up, spending by person, occasion and year, each person's
history, and the gift-tax flag. People and gifts are their owner's alone unless a person is
shared; a gift for a person linked to the viewer is never shown to them."""

import datetime as dt
from decimal import Decimal

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import false, select

from .. import access, activity, clock, gifts, ids, receipts
from ..errors import FieldError, Problem, refuse
from ..gifts import holidays
from ..store.entities.accounts import Account, Category, Transaction
from ..store.entities.education import Gift, GiftPerson, Occasion, Person
from ..store.entities.users import User
from .conventions import Model, Money
from .deps import Caller, caller, server
from .receipts import ReceiptRow
from .receipts import row as receipt_row

router = APIRouter(prefix="/ui/api", tags=["gifts"])


# ---- People and their occasions (S7.7) ----


class OccasionIn(Model):
    kind: str  # anniversary, holiday, custom
    name: str | None = None
    holiday: str | None = None
    month: int | None = None
    day: int | None = None
    year: int | None = None
    budget: Money | None = None


class OccasionOut(OccasionIn):
    id: str
    label: str
    next: dt.date | None


class PersonIn(Model):
    name: str
    relationship: str | None = None
    userId: str | None = None
    birthMonth: int | None = None
    birthDay: int | None = None
    birthYear: int | None = None
    giftBudget: Money | None = None
    leadDays: int = 14
    notes: str | None = None
    occasions: list[OccasionIn] | None = None  # when given, they replace the person's


class NextDate(Model):
    key: str
    label: str
    date: dt.date
    days: int
    turns: int | None


class PersonOut(Model):
    id: str
    name: str
    relationship: str | None
    userId: str | None
    userName: str | None
    birthMonth: int | None
    birthDay: int | None
    birthYear: int | None
    giftBudget: Money | None
    leadDays: int
    notes: str | None
    occasions: list[OccasionOut]
    next: NextDate | None
    spent: Money  # this year
    lastGift: str | None
    level: str
    ownerName: str
    version: int


class HolidayOut(Model):
    key: str
    label: str
    date: dt.date | None  # this year's


def _next(p: Person, occs: list[Occasion], today: dt.date) -> NextDate | None:
    ahead = [
        d
        for y in (today.year, today.year + 1)
        for d in gifts.dates_in(p, occs, y)
        if d.date >= today
    ]
    if not ahead:
        return None
    d = min(ahead, key=lambda x: x.date)
    return NextDate(
        key=d.key, label=d.label, date=d.date, days=(d.date - today).days, turns=d.turns
    )


def _occasion_out(o: Occasion, today: dt.date) -> OccasionOut:
    nxt = None
    for y in (today.year, today.year + 1):
        if o.kind == "holiday":
            d = holidays.date_of(o.holiday, y)
        else:
            d = gifts._safe(y, o.month, o.day)
        if d is not None and d >= today:
            nxt = d
            break
    label = holidays.label(o.holiday) if o.kind == "holiday" else (o.name or "Anniversary")
    return OccasionOut(
        id=o.id,
        kind=o.kind,
        name=o.name,
        holiday=o.holiday,
        month=o.month,
        day=o.day,
        year=o.year,
        budget=o.budget,
        label=label,
        next=nxt,
    )


def people_view(s, c: Caller) -> list[PersonOut]:
    today = clock.today()
    rows = gifts.visible_people(s, c.id)
    people = {p.id: p for p, _ in rows}
    occs = gifts.occasions_of(s, list(people))
    seen = gifts.visible_gifts(s, c.id, people)
    spent: dict[str, Decimal] = {}
    last: dict[str, tuple[int, str]] = {}
    for g, ps in seen:
        if g.status not in gifts.SPENT:
            continue
        y = gifts.gift_day(g, s) or 0
        for pid in ps:
            if y == today.year and g.cost:
                spent[pid] = spent.get(pid, Decimal(0)) + g.cost / max(len(ps), 1)
            if g.status == "given" and y >= last.get(pid, (0, ""))[0]:
                last[pid] = (y, f"{g.description}, {y}")
    out = []
    for p, lvl in rows:
        owner = s.get(User, p.ownerId)
        linked = s.get(User, p.userId) if p.userId else None
        out.append(
            PersonOut(
                id=p.id,
                name=p.name,
                relationship=p.relationship,
                userId=p.userId,
                userName=linked.displayName if linked else None,
                birthMonth=p.birthMonth,
                birthDay=p.birthDay,
                birthYear=p.birthYear,
                giftBudget=p.giftBudget,
                leadDays=p.leadDays,
                notes=p.notes,
                occasions=[_occasion_out(o, today) for o in occs[p.id]],
                next=_next(p, occs[p.id], today),
                spent=spent.get(p.id, Decimal(0)),
                lastGift=None if p.userId == c.id else last.get(p.id, (0, None))[1],
                level=lvl,
                ownerName=owner.displayName,
                version=p.version,
            )
        )
    return out


def _check_person(s, body: PersonIn) -> dict:
    e: list[FieldError] = []
    name = body.name.strip()
    if not name or len(name) > 80:
        e.append(FieldError("name", "name-invalid", "A name, up to 80 characters."))
    if body.birthMonth is not None and not 1 <= body.birthMonth <= 12:
        e.append(FieldError("birthMonth", "month-invalid", "A month, 1 to 12."))
    if body.birthDay is not None and not 1 <= body.birthDay <= 31:
        e.append(FieldError("birthDay", "day-invalid", "A day, 1 to 31."))
    if (body.birthMonth is None) != (body.birthDay is None):
        e.append(FieldError("birthDay", "birthday-incomplete", "A month and a day."))
    year = clock.today().year
    if body.birthYear is not None and not year - 120 <= body.birthYear <= year:
        e.append(FieldError("birthYear", "year-invalid", "A year of birth."))
    if body.giftBudget is not None and body.giftBudget < 0:
        e.append(FieldError("giftBudget", "amount-invalid", "Zero or more."))
    if not 0 <= body.leadDays <= 120:
        e.append(FieldError("leadDays", "lead-invalid", "0 to 120 days."))
    if body.userId and s.get(User, body.userId) is None:
        e.append(FieldError("userId", "user-unknown", "No such user."))
    for i, o in enumerate(body.occasions or []):
        at = f"occasions.{i}"
        if o.kind == "holiday":
            if o.holiday not in holidays.HOLIDAYS:
                e.append(FieldError(f"{at}.holiday", "holiday-invalid", "One of the holidays."))
        elif o.kind in ("anniversary", "custom"):
            if not (o.month and o.day and 1 <= o.month <= 12 and 1 <= o.day <= 31):
                e.append(FieldError(f"{at}.month", "date-invalid", "A month and a day."))
            if o.kind == "custom" and not (o.name or "").strip():
                e.append(FieldError(f"{at}.name", "name-missing", "What the occasion is."))
        else:
            e.append(FieldError(f"{at}.kind", "kind-invalid", "An anniversary, holiday or date."))
        if o.budget is not None and o.budget < 0:
            e.append(FieldError(f"{at}.budget", "amount-invalid", "Zero or more."))
    if e:
        raise Problem(422, e[0].code, e[0].message, e)
    return {
        "name": name,
        "relationship": (body.relationship or "").strip() or None,
        "userId": body.userId or None,
        "birthMonth": body.birthMonth,
        "birthDay": body.birthDay,
        "birthYear": body.birthYear,
        "giftBudget": body.giftBudget,
        "leadDays": body.leadDays,
        "notes": body.notes or None,
    }


def _set_occasions(s, p: Person, wanted: list[OccasionIn], user_id: str) -> None:
    for o in gifts.occasions_of(s, [p.id])[p.id]:
        o.mark_deleted(user_id)
    for o in wanted:
        holiday = o.kind == "holiday"
        s.add(
            Occasion(
                id=ids.new_id("Occsn"),
                personId=p.id,
                kind=o.kind,
                name=None if holiday else ((o.name or "").strip() or None),
                holiday=o.holiday if holiday else None,
                month=None if holiday else o.month,
                day=None if holiday else o.day,
                year=None if holiday else o.year,
                budget=o.budget,
            )
        )


def _one(s, c: Caller, person_id: str) -> PersonOut:
    return next(p for p in people_view(s, c) if p.id == person_id)


@router.get("/people", response_model=list[PersonOut])
def list_people(request: Request, c: Caller = Depends(caller)):
    """The caller's people and those shared with them."""
    with server(request).db.read() as s:
        return people_view(s, c)


@router.get("/holidays", response_model=list[HolidayOut])
def list_holidays(request: Request, c: Caller = Depends(caller)):
    year = clock.today().year
    return [
        HolidayOut(key=k, label=holidays.label(k), date=holidays.date_of(k, year))
        for k in holidays.HOLIDAYS
    ]


@router.post("/people", response_model=PersonOut, status_code=201)
def add_person(body: PersonIn, request: Request, c: Caller = Depends(caller)):
    with server(request).db.tx() as s:
        values = _check_person(s, body)
        p = Person(id=ids.new_id("Persn"), ownerId=c.id, **values)
        s.add(p)
        s.flush()
        _set_occasions(s, p, body.occasions or [], c.id)
        s.flush()
        return _one(s, c, p.id)


@router.put("/people/{person_id}", response_model=PersonOut)
def change_person(person_id: str, body: PersonIn, request: Request, c: Caller = Depends(caller)):
    with server(request).db.tx() as s:
        p, _ = gifts.person(s, c.id, person_id, "write")
        for k, v in _check_person(s, body).items():
            setattr(p, k, v)
        p.updatedAt = clock.now()
        if body.occasions is not None:
            _set_occasions(s, p, body.occasions, c.id)
        s.flush()
        return _one(s, c, p.id)


@router.delete("/people/{person_id}", status_code=204)
def delete_person(person_id: str, request: Request, c: Caller = Depends(caller)):
    with server(request).db.tx() as s:
        p, _ = gifts.person(s, c.id, person_id, "owner")
        p.mark_deleted(c.id)
    return Response(status_code=204)


# ---- Gifts (S7.8) ----


class PersonRef(Model):
    id: str
    name: str


class Paid(Model):
    transactionId: str
    date: dt.date
    amount: Money
    payee: str | None
    accountName: str


class GiftIn(Model):
    people: list[str]
    occasion: str | None = None  # birthday, holiday:<key>, occasion:<id>; none for an idea
    occasionYear: int | None = None
    description: str
    status: str = "idea"
    cost: Money | None = None
    transactionId: str | None = None
    store: str | None = None
    link: str | None = None
    notes: str | None = None
    cash: bool = False
    thankYou: bool = False


class GiftOut(Model):
    id: str
    people: list[PersonRef]
    occasion: str | None
    occasionLabel: str
    occasionYear: int | None
    description: str
    status: str
    cost: Money | None
    paid: Paid | None
    store: str | None
    link: str | None
    notes: str | None
    cash: bool
    thankYou: bool
    documents: list[ReceiptRow]
    canWrite: bool
    version: int


def _paid(s, t_id: str | None) -> Paid | None:
    t = s.get(Transaction, t_id) if t_id else None
    if t is None or t.deleted:
        return None
    a = s.get(Account, t.accountId)
    return Paid(transactionId=t.id, date=t.date, amount=t.amount, payee=t.payee, accountName=a.name)


def _gift_out(s, c: Caller, g: Gift, ps: list[str], people: dict, levels: dict) -> GiftOut:
    occs = gifts.occasions_of(s, ps)
    can = g.ownerId == c.id or (
        bool(ps) and all(access.RANK.get(levels.get(pid, ""), 0) >= 2 for pid in ps)
    )
    return GiftOut(
        id=g.id,
        people=[PersonRef(id=pid, name=people[pid].name) for pid in ps if pid in people],
        occasion=g.occasion,
        occasionLabel=gifts.label_of(g.occasion, [o for v in occs.values() for o in v]),
        occasionYear=g.occasionYear,
        description=g.description,
        status=g.status,
        cost=g.cost,
        paid=_paid(s, g.transactionId),
        store=g.store,
        link=g.link,
        notes=g.notes,
        cash=g.cash,
        thankYou=g.thankYou,
        documents=[
            receipt_row(s, r, receipts.level(s, c.id, r) or "read")
            for r in receipts.of_item(s, g.id, "gift")
        ],
        canWrite=can,
        version=g.version,
    )


def gifts_view(s, c: Caller, status: str | None = None, person: str | None = None):
    rows = gifts.visible_people(s, c.id)
    people = {p.id: p for p, _ in rows}
    levels = {p.id: lvl for p, lvl in rows}
    out = []
    for g, ps in gifts.visible_gifts(s, c.id, people):
        if status and g.status != status:
            continue
        if person and person not in ps:
            continue
        out.append(_gift_out(s, c, g, ps, people, levels))
    order = {k: i for i, k in enumerate(gifts.STATUSES)}
    return sorted(out, key=lambda x: (order[x.status], -(x.occasionYear or 9999), x.description))


def _check_gift(s, c: Caller, body: GiftIn) -> dict:
    e: list[FieldError] = []
    desc = body.description.strip()
    if not desc:
        e.append(FieldError("description", "description-missing", "What it is."))
    if body.status not in gifts.STATUSES:
        e.append(FieldError("status", "status-invalid", "Idea, planned, bought, given, received."))
    if not body.people:
        e.append(FieldError("people", "people-missing", "Who it is for."))
    if body.cost is not None and body.cost < 0:
        e.append(FieldError("cost", "amount-invalid", "Zero or more."))
    if body.occasion and not body.occasionYear:
        e.append(FieldError("occasionYear", "year-missing", "The year of the occasion."))
    if e:
        raise Problem(422, e[0].code, e[0].message, e)
    for pid in body.people:
        gifts.person(s, c.id, pid, "write")
    if body.transactionId:
        t = s.get(Transaction, body.transactionId)
        if t is None or t.deleted:
            raise refuse("transactionId", "not-found", "No such transaction.")
        access.account(s, c.id, t.accountId, "read")
    return {
        "occasion": body.occasion or None,
        "occasionYear": body.occasionYear if body.occasion else None,
        "description": desc,
        "status": body.status,
        "cost": body.cost,
        "transactionId": body.transactionId or None,
        "store": (body.store or "").strip() or None,
        "link": (body.link or "").strip() or None,
        "notes": body.notes or None,
        "cash": body.cash,
        "thankYou": body.thankYou and body.status == "received",
    }


def _set_people(s, g: Gift, ids_: list[str], user_id: str) -> None:
    now = clock.now()
    have = {
        gp.personId: gp for gp in s.scalars(select(GiftPerson).where(GiftPerson.giftId == g.id))
    }
    for pid, gp in have.items():
        if pid not in ids_ and not gp.deleted:
            gp.deleted, gp.deletedAt, gp.deletedById = True, now, user_id
    for pid in ids_:
        gp = have.get(pid)
        if gp is None:
            s.add(GiftPerson(giftId=g.id, personId=pid, createdAt=now))
        elif gp.deleted:
            gp.deleted, gp.deletedAt, gp.deletedById = False, None, None


def _categorise(s, t_id: str | None) -> None:
    """A gift's purchase goes under Gifts in budgets (S7.8.4), unless already categorised."""
    t = s.get(Transaction, t_id) if t_id else None
    if t is None or t.categoryId:
        return
    cat = s.scalars(select(Category).where(Category.builtIn == "gifts")).first()
    if cat is not None:
        t.categoryId = cat.id


def _gift_for(s, c: Caller, gift_id: str) -> GiftOut:
    return next(x for x in gifts_view(s, c) if x.id == gift_id)


@router.get("/gifts", response_model=list[GiftOut])
def list_gifts(
    request: Request,
    status: str | None = None,
    person: str | None = None,
    c: Caller = Depends(caller),
):
    with server(request).db.read() as s:
        return gifts_view(s, c, status, person)


@router.post("/gifts", response_model=GiftOut, status_code=201)
def add_gift(body: GiftIn, request: Request, c: Caller = Depends(caller)):
    with server(request).db.tx() as s:
        values = _check_gift(s, c, body)
        g = Gift(id=ids.new_id("Gift"), ownerId=c.id, **values)
        s.add(g)
        s.flush()
        _set_people(s, g, body.people, c.id)
        _categorise(s, g.transactionId)
        s.flush()
        activity.record(s, "gift.saved", actor=c.id, owner=c.id)
        return _gift_for(s, c, g.id)


def _editable(s, c: Caller, gift_id: str) -> Gift:
    g = s.get(Gift, gift_id)
    if g is None or g.deleted:
        raise Problem(404, "not-found", "Not found")
    found = [x for x in gifts_view(s, c) if x.id == gift_id]
    if not found:
        raise Problem(404, "not-found", "Not found")
    if not found[0].canWrite:
        raise Problem(403, "read-only", "This gift is shared with you to read.")
    return g


@router.put("/gifts/{gift_id}", response_model=GiftOut)
def change_gift(gift_id: str, body: GiftIn, request: Request, c: Caller = Depends(caller)):
    with server(request).db.tx() as s:
        g = _editable(s, c, gift_id)
        for k, v in _check_gift(s, c, body).items():
            setattr(g, k, v)
        g.updatedAt = clock.now()
        _set_people(s, g, body.people, c.id)
        _categorise(s, g.transactionId)
        s.flush()
        return _gift_for(s, c, g.id)


@router.delete("/gifts/{gift_id}", status_code=204)
def delete_gift(gift_id: str, request: Request, c: Caller = Depends(caller)):
    with server(request).db.tx() as s:
        _editable(s, c, gift_id).mark_deleted(c.id)
    return Response(status_code=204)


class DocumentIn(Model):
    receiptId: str


@router.post("/gifts/{gift_id}/documents", response_model=GiftOut)
def attach_receipt(gift_id: str, body: DocumentIn, request: Request, c: Caller = Depends(caller)):
    from ..store.entities.receipts import ReceiptLink

    with server(request).db.tx() as s:
        g = _editable(s, c, gift_id)
        r, _ = receipts.get(s, c.id, body.receiptId)
        if s.get(ReceiptLink, (r.id, "gift", g.id)) is None:
            s.add(
                ReceiptLink(
                    receiptId=r.id,
                    kind="gift",
                    itemId=g.id,
                    createdAt=clock.now(),
                    linkedById=c.id,
                )
            )
        s.flush()
        return _gift_for(s, c, g.id)


class Purchase(Model):
    transactionId: str
    date: dt.date
    amount: Money
    payee: str | None
    accountName: str
    category: str | None


@router.get("/gifts/purchases", response_model=list[Purchase])
def purchases(request: Request, c: Caller = Depends(caller)):
    """Recent spending, to link a gift's cost to its transaction: the last 90 days."""
    with server(request).db.read() as s:
        accts = {a.id: a for a, _ in access.visible_accounts(s, c.id)}
        if not accts:
            return []
        cats = {x.id: x.name for x in s.scalars(select(Category))}
        rows = s.scalars(
            select(Transaction)
            .where(
                Transaction.accountId.in_(list(accts)),
                Transaction.deleted == false(),
                Transaction.amount < 0,
                Transaction.transferId.is_(None),
                Transaction.instrumentId.is_(None),
                Transaction.date >= clock.today() - dt.timedelta(days=90),
            )
            .order_by(Transaction.date.desc())
            .limit(200)
        )
        return [
            Purchase(
                transactionId=t.id,
                date=t.date,
                amount=t.amount,
                payee=t.payee,
                accountName=accts[t.accountId].name,
                category=cats.get(t.categoryId),
            )
            for t in rows
        ]


# ---- Upcoming, spending and history ----


class UpcomingOut(Model):
    person: PersonRef
    key: str
    label: str
    date: dt.date
    days: int
    turns: int | None
    inLead: bool
    budget: Money | None
    planned: Money
    missing: str
    gifts: list[GiftOut]


@router.get("/gifts/upcoming", response_model=list[UpcomingOut])
def list_upcoming(request: Request, c: Caller = Depends(caller)):
    with server(request).db.read() as s:
        rows = gifts.visible_people(s, c.id)
        people = {p.id: p for p, _ in rows}
        levels = {p.id: lvl for p, lvl in rows}
        out = []
        for u in gifts.upcoming(s, c.id, clock.today()):
            ps = gifts.people_of_gifts(s, [g.id for g in u.gifts])
            out.append(
                UpcomingOut(
                    person=PersonRef(id=u.person.id, name=u.person.name),
                    key=u.date.key,
                    label=u.date.label,
                    date=u.date.date,
                    days=u.days,
                    turns=u.date.turns,
                    inLead=u.inLead,
                    budget=u.date.budget,
                    planned=u.planned,
                    missing=gifts.what_is_missing(u),
                    gifts=[_gift_out(s, c, g, ps[g.id], people, levels) for g in u.gifts],
                )
            )
        return out


class PersonSpend(Model):
    person: PersonRef
    spent: Money
    budget: Money | None


class Amount(Model):
    label: str
    amount: Money


class Flag(Model):
    person: PersonRef
    given: Money
    exclusion: Money


class SpendingOut(Model):
    year: int
    byPerson: list[PersonSpend]
    byOccasion: list[Amount]
    byYear: list[Amount]
    flagged: list[Flag]


@router.get("/gifts/spending", response_model=SpendingOut)
def get_spending(request: Request, year: int | None = None, c: Caller = Depends(caller)):
    with server(request).db.read() as s:
        sp = gifts.spending(s, c.id, year or clock.today().year)
        return SpendingOut(
            year=sp.year,
            byPerson=[
                PersonSpend(person=PersonRef(id=p.id, name=p.name), spent=a, budget=b)
                for p, a, b in sp.byPerson
            ],
            byOccasion=[Amount(label=k, amount=v) for k, v in sp.byOccasion],
            byYear=[Amount(label=str(k), amount=v) for k, v in sp.byYear],
            flagged=[
                Flag(person=PersonRef(id=p.id, name=p.name), given=a, exclusion=x)
                for p, a, x in sp.flagged
            ],
        )
