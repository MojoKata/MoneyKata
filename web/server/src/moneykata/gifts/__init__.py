"""Gifts (requirements S7.7, S7.8): people and their occasions, what each user may see (a
person's owner, or those it is shared with, but never the gifts for themselves), the occasions
coming up with what is planned for them, spending by person, occasion and year, and the
gift-tax flag."""

import datetime as dt
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import false, or_, select
from sqlalchemy.orm import Session

from .. import access
from ..projections import taxtables
from ..store.entities.education import Gift, GiftPerson, Occasion, Person
from . import holidays

ZERO = Decimal(0)
UPCOMING_DAYS = 60
STATUSES = ("idea", "planned", "bought", "given", "received")
SPENT = ("bought", "given")


def visible_people(s: Session, user_id: str) -> list[tuple[Person, str]]:
    """The user's own people, and those shared with them, with the level of each."""
    r = access.reach(s, user_id)
    shared = [i for (k, i) in r.levels if k == "person"]
    rows = s.scalars(
        select(Person)
        .where(Person.deleted == false(), or_(Person.ownerId == user_id, Person.id.in_(shared)))
        .order_by(Person.name)
    ).all()
    out = []
    for p in rows:
        lvl = access.level_of(s, user_id, "person", p.ownerId, p.id, p.deleted, r)
        if lvl is not None:
            out.append((p, lvl))
    return out


def person(s: Session, user_id: str, person_id: str, need: str = "read") -> tuple[Person, str]:
    from ..errors import Problem

    p = s.get(Person, person_id)
    lvl = access.level_of(s, user_id, "person", p.ownerId, p.id, p.deleted) if p else None
    if lvl is None:
        raise Problem(404, "not-found", "Not found")
    if access.RANK[lvl] < access.RANK[need]:
        raise Problem(403, "read-only", "This person is shared with you to read.")
    return p, lvl


def occasions_of(s: Session, person_ids: list[str]) -> dict[str, list[Occasion]]:
    out: dict[str, list[Occasion]] = {i: [] for i in person_ids}
    if not person_ids:
        return out
    for o in s.scalars(
        select(Occasion)
        .where(Occasion.personId.in_(person_ids), Occasion.deleted == false())
        .order_by(Occasion.createdAt)
    ):
        out[o.personId].append(o)
    return out


def people_of_gifts(s: Session, gift_ids: list[str]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {i: [] for i in gift_ids}
    if not gift_ids:
        return out
    for gp in s.scalars(
        select(GiftPerson).where(GiftPerson.giftId.in_(gift_ids), GiftPerson.deleted == false())
    ):
        out[gp.giftId].append(gp.personId)
    return out


def visible_gifts(
    s: Session, user_id: str, people: dict[str, Person]
) -> list[tuple[Gift, list[str]]]:
    """Gifts for (or from) the people the user can see, and their own gifts; never a gift for
    a person linked to the user, even through a share, so a surprise stays one (S7.8.5)."""
    ids = list(people)
    # Anyone's person who is the viewer: on another user's list, so maybe not visible here.
    linked_to_me = set(
        s.scalars(select(Person.id).where(Person.userId == user_id, Person.deleted == false()))
    )
    gift_ids = set(
        s.scalars(
            select(GiftPerson.giftId).where(
                GiftPerson.personId.in_(ids), GiftPerson.deleted == false()
            )
        )
    )
    rows = s.scalars(
        select(Gift).where(
            Gift.deleted == false(), or_(Gift.id.in_(gift_ids), Gift.ownerId == user_id)
        )
    ).all()
    whom = people_of_gifts(s, [g.id for g in rows])
    out = []
    for g in rows:
        ps = whom[g.id]
        if g.status != "received" and any(p in linked_to_me for p in ps):
            continue
        out.append((g, ps))
    return out


@dataclass
class Date:
    key: str  # birthday, holiday:<key> or occasion:<id>
    label: str
    date: dt.date
    budget: Decimal | None
    kind: str  # birthday, anniversary, holiday, custom
    turns: int | None = None  # a birthday's age, an anniversary's count


def _safe(year: int, month: int, day: int) -> dt.date:
    try:
        return dt.date(year, month, day)
    except ValueError:  # 29 February
        return dt.date(year, month, 28)


def dates_in(p: Person, occs: list[Occasion], year: int) -> list[Date]:
    """A person's dated occasions in a year."""
    out = []
    if p.birthMonth and p.birthDay:
        out.append(
            Date(
                "birthday",
                "Birthday",
                _safe(year, p.birthMonth, p.birthDay),
                None,
                "birthday",
                year - p.birthYear if p.birthYear else None,
            )
        )
    for o in occs:
        if o.kind == "holiday":
            day = holidays.date_of(o.holiday, year)
            if day is not None:
                key = f"holiday:{o.holiday}"
                out.append(Date(key, holidays.label(o.holiday), day, o.budget, "holiday"))
        else:
            label = o.name or ("Anniversary" if o.kind == "anniversary" else "Occasion")
            out.append(
                Date(
                    f"occasion:{o.id}",
                    label,
                    _safe(year, o.month, o.day),
                    o.budget,
                    o.kind,
                    year - o.year if o.year else None,
                )
            )
    return out


def label_of(key: str | None, occs: list[Occasion]) -> str:
    if not key:
        return "An idea"
    if key == "birthday":
        return "Birthday"
    kind, _, ident = key.partition(":")
    if kind == "holiday" and ident in holidays.HOLIDAYS:
        return holidays.label(ident)
    o = next((x for x in occs if x.id == ident), None)
    return (o.name or "Anniversary") if o else "An occasion"


@dataclass
class Upcoming:
    person: Person
    date: Date
    days: int
    inLead: bool
    gifts: list[Gift] = field(default_factory=list)
    planned: Decimal = ZERO  # what the gifts for it cost so far


def upcoming(s: Session, user_id: str, today: dt.date, days: int = UPCOMING_DAYS) -> list[Upcoming]:
    """Everyone's dates in the next 60 days, each with the gifts for it (S7.7.3)."""
    people = dict((p.id, p) for p, _ in visible_people(s, user_id))
    occs = occasions_of(s, list(people))
    gifts = visible_gifts(s, user_id, people)
    end = today + dt.timedelta(days=days)
    out = []
    for p in people.values():
        if p.userId == user_id:
            continue  # your own dates are for others to plan
        for year in {today.year, end.year}:
            for d in dates_in(p, occs[p.id], year):
                if not today <= d.date <= end:
                    continue
                left = (d.date - today).days
                mine = [
                    g
                    for g, ps in gifts
                    if p.id in ps
                    and g.occasion == d.key
                    and g.occasionYear == d.date.year
                    and g.status != "received"
                ]
                out.append(
                    Upcoming(
                        p,
                        d,
                        left,
                        left <= p.leadDays,
                        mine,
                        sum((g.cost or ZERO for g in mine if g.status != "idea"), ZERO),
                    )
                )
    return sorted(out, key=lambda u: (u.date.date, u.person.name))


def what_is_missing(u: Upcoming) -> str:
    """'no gift yet', '1 idea, nothing bought', or what is planned."""
    if not u.gifts:
        return "no gift yet"
    ideas = sum(1 for g in u.gifts if g.status == "idea")
    done = [g for g in u.gifts if g.status in ("bought", "given")]
    if done:
        return f"{len(done)} bought"
    if ideas == len(u.gifts):
        return f"{ideas} idea{'' if ideas == 1 else 's'}, nothing bought"
    return f"{len(u.gifts) - ideas} planned, nothing bought"


def gift_day(g: Gift, s: Session) -> int | None:
    """The year a gift's spending counts in: its occasion's, else its purchase's."""
    if g.occasionYear:
        return g.occasionYear
    if g.transactionId:
        from ..store.entities.accounts import Transaction

        t = s.get(Transaction, g.transactionId)
        return t.date.year if t else None
    return None


@dataclass
class Spending:
    year: int
    byPerson: list[tuple[Person, Decimal, Decimal | None]]  # spent, budget
    byOccasion: list[tuple[str, Decimal]]
    byYear: list[tuple[int, Decimal]]
    flagged: list[tuple[Person, Decimal, Decimal]]  # given in money above the exclusion


def spending(s: Session, user_id: str, year: int) -> Spending:
    people = dict((p.id, p) for p, _ in visible_people(s, user_id))
    by_person: dict[str, Decimal] = defaultdict(lambda: ZERO)
    by_occasion: dict[str, Decimal] = defaultdict(lambda: ZERO)
    by_year: dict[int, Decimal] = defaultdict(lambda: ZERO)
    money: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for g, ps in visible_gifts(s, user_id, people):
        if g.status not in SPENT or not g.cost:
            continue
        y = gift_day(g, s)
        if y is None:
            continue
        by_year[y] += g.cost
        if y != year:
            continue
        share = g.cost / max(len(ps), 1)
        for pid in ps:
            by_person[pid] += share
            if g.cash and g.ownerId == user_id:
                money[pid] += share
        kind = (g.occasion or "other").partition(":")[0]
        name = {
            "birthday": "Birthdays",
            "holiday": label_of(g.occasion, []),
            "occasion": "Anniversaries and other dates",
        }.get(kind, "Other")
        by_occasion[name] += g.cost
    # 529 contributions to the person are gifts to them too (S1.8.2, S7.8.7).
    from .. import education
    from ..store.entities.accounts import Account
    from ..store.entities.education import EducationPlan

    for plan in s.scalars(
        select(EducationPlan).where(
            EducationPlan.beneficiaryPersonId.in_(list(people)), EducationPlan.deleted == false()
        )
    ):
        a = s.get(Account, plan.accountId)
        if a is None or a.deleted or a.ownerId != user_id:
            continue
        for r in education.contributions(s, a):
            if r.contributor == "owner" and r.date.year == year and not r.fiveYear:
                money[plan.beneficiaryPersonId] += r.amount
    limit = Decimal(str(taxtables.figures(s, year)["giftExclusion"]))
    return Spending(
        year=year,
        byPerson=[
            (p, by_person.get(p.id, ZERO), p.giftBudget)
            for p in people.values()
            if p.userId != user_id
        ],
        byOccasion=sorted(by_occasion.items(), key=lambda x: -x[1]),
        byYear=sorted(by_year.items()),
        flagged=[(people[pid], amt, limit) for pid, amt in money.items() if amt > limit],
    )


def label_for_occasion(s: Session, g: Gift, ps: list[str]) -> str:
    occs = occasions_of(s, ps)
    return label_of(g.occasion, [o for v in occs.values() for o in v])
