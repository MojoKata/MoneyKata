"""Dev mode's gifts (requirements S17.7): Alice's people with their dates (Emma, Margaret, and
Bob as a person linked to his user), gifts from idea to given across this year and last, one
received with its thank-you, and Emma shared with Bob so they plan her gifts together."""

from decimal import Decimal as D

from sqlalchemy import select

from .. import clock, ids
from ..store.entities.education import Gift, GiftPerson, Occasion, Person
from ..store.entities.sharing import Share


def seed_gifts(s, people: dict) -> None:
    alice, bob = people["alice"], people["bob"]
    year = clock.today().year
    now = clock.now()
    emma = s.scalars(select(Person).where(Person.name == "Emma Griffin")).one()
    margaret = s.scalars(select(Person).where(Person.name == "Margaret Griffin")).one()
    him = Person(
        id=ids.new_id("Persn"),
        ownerId=alice.id,
        name="Bob Griffin",
        relationship="husband",
        userId=bob.id,
        birthMonth=4,
        birthDay=2,
        birthYear=1977,
        giftBudget=D(800),
        notes="Size L. Wants a new watch strap.",
    )
    s.add(him)
    s.flush()

    def occasion(p, kind, **kw):
        s.add(Occasion(id=ids.new_id("Occsn"), personId=p.id, kind=kind, **kw))

    occasion(emma, "holiday", holiday="christmas", budget=D(150))
    occasion(margaret, "holiday", holiday="christmas", budget=D(80))
    occasion(margaret, "holiday", holiday="mothers-day")
    occasion(him, "holiday", holiday="christmas")
    occasion(him, "holiday", holiday="valentines")
    occasion(
        him, "anniversary", name="Wedding anniversary", month=6, day=12, year=2010, budget=D(200)
    )
    margaret.giftBudget = D(300)

    def gift(whom, description, status, occ=None, y=None, cost=None, **kw):
        g = Gift(
            id=ids.new_id("Gift"),
            ownerId=alice.id,
            description=description,
            status=status,
            occasion=occ,
            occasionYear=y if occ else None,
            cost=D(cost) if cost else None,
            **kw,
        )
        s.add(g)
        s.flush()
        for p in whom:
            s.add(GiftPerson(giftId=g.id, personId=p.id, createdAt=now))

    gift([emma], "Watercolour set", "idea", "birthday", year)
    gift([emma], "Riding lessons, a block of five", "planned", "birthday", year, "180")
    gift([emma], "Horse encyclopedia", "idea")
    gift([emma], "LEGO castle", "given", "birthday", year - 1, "89.99")
    gift([emma], "Art easel", "given", "holiday:christmas", year - 1, "64.00")
    gift([margaret], "Framed photo of Emma", "given", "holiday:mothers-day", year, "45.00")
    gift([margaret], "Wool scarf", "received", "holiday:christmas", year - 1, thankYou=True)
    gift([him], "Watch strap, brown leather", "planned", "holiday:christmas", year, "120")
    gift([him], "Weekend away", "given", f"occasion:{_anniversary(s, him)}", year, "640.00")
    gift(
        [emma, him],
        "Board game for the family",
        "bought",
        "holiday:christmas",
        year,
        "39.99",
        store="Target",
    )
    s.add(
        Share(
            id=ids.new_id("Share"),
            kind="person",
            itemId=emma.id,
            level="write",
            userId=bob.id,
            createdById=alice.id,
        )
    )


def _anniversary(s, p: Person) -> str:
    s.flush()
    return s.scalars(
        select(Occasion.id).where(Occasion.personId == p.id, Occasion.kind == "anniversary")
    ).one()
