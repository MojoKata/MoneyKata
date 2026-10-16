"""People and relationships (requirements S10.10): the household's people, each added once and
changed only by themselves, whoever added them or an admin; asking to share a private one;
dated relationships, added by those in them or by an admin; and the family tree worked out
from them as of a day."""

import datetime as dt

from fastapi import APIRouter, Depends, Request
from sqlalchemy import false, select

from .. import activity, clock, gifts, ids, people
from ..errors import Problem, refuse
from ..people import tree
from ..store.entities.education import Person, Relationship
from ..store.entities.users import User
from .conventions import Deleted, ExactRoute, Model, check, gone, if_match
from .deps import Caller, caller, server
from .gifts import check_person_fields, refuse_clash

router = APIRouter(prefix="/ui/api", route_class=ExactRoute, tags=["people"])


class PersonIn(Model):
    name: str
    sex: str | None = None
    birthMonth: int | None = None
    birthDay: int | None = None
    birthYear: int | None = None
    diedOn: dt.date | None = None
    private: bool = False
    differentPerson: bool = False  # the same name as someone here, told apart by birth year


class PersonRow(Model):
    id: str
    name: str
    sex: str
    birthMonth: int | None
    birthDay: int | None
    birthYear: int | None
    diedOn: dt.date | None
    private: bool
    userId: str | None  # when they are a user
    relation: str | None  # to the caller (S10.10.5)
    canChange: bool
    createdBy: str | None
    version: int


def _rows(s, c: Caller) -> list[PersonRow]:
    me = s.get(User, c.id)
    words = tree.relation_to(s, me.personId)
    users = people.users_by_person(s)
    out = []
    for p, lvl in people.visible(s, c.id):
        u = users.get(p.id)
        creator = s.get(User, p.ownerId) if p.ownerId else None
        rel = words.get(p.id)
        out.append(
            PersonRow(
                id=p.id,
                name=p.name,
                sex=p.sex,
                birthMonth=p.birthMonth,
                birthDay=p.birthDay,
                birthYear=p.birthYear,
                diedOn=p.diedOn,
                private=p.private,
                userId=u.id if u else None,
                relation=rel.word if rel else ("you" if p.id == me.personId else None),
                canChange=lvl == "owner",
                createdBy=creator.displayName if creator else None,
                version=p.version,
            )
        )
    return out


def _row(s, c: Caller, person_id: str) -> PersonRow:
    return next(r for r in _rows(s, c) if r.id == person_id)


@router.get("/persons", response_model=list[PersonRow])
def list_persons(request: Request, c: Caller = Depends(caller)):
    """The household's people the caller can see, with how each is related to them."""
    with server(request).db.read() as s:
        return _rows(s, c)


@router.post("/persons", response_model=PersonRow, status_code=201)
def add_person(body: PersonIn, request: Request, c: Caller = Depends(caller)):
    """A person, added once (S10.10.3)."""
    with server(request).db.tx() as s:
        values = check_person_fields(body)
        if not body.differentPerson:
            refuse_clash(s, c, values["name"], values["birthYear"])
        elif people.clash(s, values["name"], values["birthYear"]) is not None:
            raise refuse(
                "birthYear",
                "not-told-apart",
                "Give both birth years, different ones, to tell them apart.",
            )
        p = Person(
            id=ids.new_id("Persn"),
            ownerId=c.id,
            private=body.private,
            **values,
        )
        s.add(p)
        s.flush()
        return _row(s, c, p.id)


@router.patch("/persons/{person_id}", response_model=PersonRow)
def change_person(
    person_id: str,
    body: PersonIn,
    request: Request,
    c: Caller = Depends(caller),
    version: int = Depends(if_match),
):
    """Only the person, whoever added them, or an admin changes them (S10.10.2)."""
    with server(request).db.tx() as s:
        p = people.get(s, c.id, person_id, "owner")
        check(p, version, lambda: _row(s, c, p.id))
        values = check_person_fields(body)
        if (values["name"], values["birthYear"]) != (p.name, p.birthYear):
            refuse_clash(s, c, values["name"], values["birthYear"], exclude=p.id)
        if body.diedOn and body.diedOn > clock.today():
            raise refuse("diedOn", "date-invalid", "A day that has passed.")
        died = p.diedOn != body.diedOn
        values["diedOn"] = body.diedOn
        values["private"] = body.private
        people.change(s, p, values)
        s.flush()
        if died:  # a death ends a marriage on that day (S10.10.4.2)
            _rewash(
                s,
                *[
                    (r.relation, r.person1Id, r.person2Id)
                    for r in people.live_relationships(s, [p.id])
                ],
            )
        return _row(s, c, p.id)


@router.delete("/persons/{person_id}", response_model=Deleted[None])
def delete_person(
    person_id: str, request: Request, c: Caller = Depends(caller), version: int = Depends(if_match)
):
    """A person who isn't a user. Gifts bought, given or received keep them by name; ideas and
    planned gifts for them alone go with them (S7.8.6)."""
    with server(request).db.tx() as s:
        p = people.get(s, c.id, person_id, "owner")
        check(p, version, lambda: _row(s, c, p.id))
        if people.user_of(s, p.id) is not None:
            raise refuse(None, "person-is-user", "A user's person stays; make the user inactive.")
        gifts.delete_person(s, p, c.id)
        s.flush()
        return Deleted[None](deleted=gone(p))


class Asked(Model):
    asked: bool


class JoinIn(Model):
    userId: str  # the remote user who is this person


@router.post("/persons/{person_id}/join", response_model=PersonRow)
def join_person(person_id: str, body: JoinIn, request: Request, c: Caller = Depends(caller)):
    """A remote user is this person (S10.10.1): confirmed by someone who may change it."""
    with server(request).db.tx() as s:
        p = people.get(s, c.id, person_id, "owner")
        remote = s.get(User, body.userId)
        if remote is None or remote.linkId is None:
            raise Problem(404, "not-found", "Not found")
        people.join(s, c.id, p, remote)
        activity.record(s, "person.joined", actor=c.id, owner=c.id)
        s.flush()
        return _row(s, c, p.id)


@router.post("/persons/{person_id}/ask-to-share", response_model=Asked)
def ask_to_share(person_id: str, request: Request, c: Caller = Depends(caller)):
    """Ask whoever added a private person, and the admins, to share them (S10.10.3)."""
    with server(request).db.tx() as s:
        p = s.get(Person, person_id)
        if p is None or p.deleted or not p.private:
            raise Problem(404, "not-found", "Not found")
        if people.level(s, c.id, p) is not None:
            return Asked(asked=False)
        activity.record(
            s,
            "person.share-asked",
            actor=c.id,
            subject_kind="person",
            subject_id=p.id,
            owner=p.ownerId,
            for_admins=True,
        )
        return Asked(asked=True)


class RelationOut(Model):
    personId: str
    name: str
    key: str  # parent, sibling, step-parent… or friend, colleague, family
    word: str  # in their sex: mother, brother-in-law
    stored: bool
    label: str | None


@router.get("/persons/{person_id}/relations", response_model=list[RelationOut])
def person_relations(
    person_id: str, request: Request, on: dt.date | None = None, c: Caller = Depends(caller)
):
    """Everyone the person is related to as of a day, stored and worked out (S10.10.5)."""
    with server(request).db.read() as s:
        people.get(s, c.id, person_id)
        g = tree.graph(s, on or clock.today())
        return [
            RelationOut(
                personId=r.personId,
                name=g.people[r.personId].name,
                key=r.key,
                word=r.word,
                stored=r.stored,
                label=r.label,
            )
            for r in g.relations(person_id)
            if people.level(s, c.id, g.people[r.personId]) is not None
        ]


# ---- Relationships (S10.10.4) ----


class Named(Model):
    id: str
    name: str
    deleted: bool


class RelationshipIn(Model):
    person1Id: str
    person2Id: str
    relation: str  # spouse, couple, child (person1 the parent), friend, colleague, family
    label: str | None = None
    fromDate: dt.date | None = None
    toDate: dt.date | None = None


class RelationshipOut(Model):
    id: str
    person1: Named
    person2: Named
    relation: str
    label: str | None
    fromDate: dt.date | None
    toDate: dt.date | None
    endsOn: dt.date | None  # its end, or for a marriage the first death
    # A marriage's confirmations (S10.10.4): None for the other relations; until both, it
    # counts for gifts only. canConfirm: this user may confirm a side still waiting.
    confirmed: bool | None
    waitingFor: list[Named]
    canConfirm: bool
    canChange: bool
    version: int


def _named(s, person_id: str) -> Named:
    p = s.get(Person, person_id)
    return Named(id=p.id, name=p.name, deleted=p.deleted)


def _rel_out(s, c: Caller, r: Relationship) -> RelationshipOut:
    waiting = (
        [
            _named(s, pid)
            for pid, at in ((r.person1Id, r.confirmed1At), (r.person2Id, r.confirmed2At))
            if at is None
        ]
        if r.relation == "spouse"
        else []
    )
    return RelationshipOut(
        id=r.id,
        person1=_named(s, r.person1Id),
        person2=_named(s, r.person2Id),
        relation=r.relation,
        label=r.label,
        fromDate=r.fromDate,
        toDate=r.toDate,
        endsOn=people.ended_on(s, r),
        confirmed=people.confirmed(r) if r.relation == "spouse" else None,
        waitingFor=waiting,
        canConfirm=any(people.may_confirm(s, c.id, w.id) for w in waiting),
        canChange=people.may_relate(s, c.id, r.person1Id, r.person2Id),
        version=r.version,
    )


@router.get("/relationships", response_model=list[RelationshipOut])
def list_relationships(request: Request, person: str | None = None, c: Caller = Depends(caller)):
    """The stored relationships of a person (the caller's own by default)."""
    with server(request).db.read() as s:
        me = s.get(User, c.id)
        pid = person or me.personId
        people.get(s, c.id, pid)
        rows = [
            r
            for r in people.live_relationships(s, [pid])
            if all(
                (x := s.get(Person, i)) is not None
                and (x.deleted or people.level(s, c.id, x) is not None)
                for i in (r.person1Id, r.person2Id)
            )
        ]
        rows.sort(key=lambda r: (r.relation, r.fromDate or dt.date.min))
        return [_rel_out(s, c, r) for r in rows]


def _apply(s, c: Caller, r: Relationship, body: RelationshipIn) -> None:
    for i in (body.person1Id, body.person2Id):
        people.get(s, c.id, i)
    if not people.may_relate(s, c.id, body.person1Id, body.person2Id):
        raise Problem(403, "not-in-it", "You add relationships you are in; an admin adds any.")
    a, b = people.ordered(body.relation, body.person1Id, body.person2Id)
    r.person1Id, r.person2Id, r.relation = a, b, body.relation
    r.label = (body.label or "").strip() or None if body.relation == "family" else None
    r.fromDate, r.toDate = body.fromDate, body.toDate
    people.check(s, r)
    dup = s.scalars(
        select(Relationship).where(
            Relationship.person1Id == a,
            Relationship.person2Id == b,
            Relationship.relation == r.relation,
            Relationship.fromDate.is_(None)
            if r.fromDate is None
            else Relationship.fromDate == r.fromDate,
            Relationship.deleted == false(),
            Relationship.id != r.id,
        )
    ).first()
    if dup is not None:
        raise refuse("relation", "relationship-exists", "That relationship is already here.", 409)


def _rewash(s, *rels: tuple[str, str, str]) -> None:
    """A marriage that begins, ends or changes its dates changes whose trades are wash sales
    (S3.8): the users in it have theirs worked out again."""
    from .. import washes

    users = set()
    for relation, a, b in rels:
        if relation == "spouse":
            users |= {u.id for u in (people.user_of(s, a), people.user_of(s, b)) if u}
    s.flush()
    for uid in sorted(users):
        washes.recompute(s, uid)


@router.post("/relationships", response_model=RelationshipOut, status_code=201)
def add_relationship(body: RelationshipIn, request: Request, c: Caller = Depends(caller)):
    with server(request).db.tx() as s:
        r = Relationship(
            id=ids.new_id("Rltn"),
            person1Id=body.person1Id,
            person2Id=body.person2Id,
            relation=body.relation,
        )
        _apply(s, c, r, body)
        people.confirm(s, c.id, r, fresh=True)
        s.add(r)
        s.flush()
        _rewash(s, (r.relation, r.person1Id, r.person2Id))
        activity.record(s, "relationship.saved", actor=c.id, owner=c.id)
        return _rel_out(s, c, r)


def _editable(s, c: Caller, rel_id: str) -> Relationship:
    r = s.get(Relationship, rel_id)
    if r is None or r.deleted:
        raise Problem(404, "not-found", "Not found")
    for i in (r.person1Id, r.person2Id):
        people.get(s, c.id, i)
    if not people.may_relate(s, c.id, r.person1Id, r.person2Id):
        raise Problem(403, "not-in-it", "You change relationships you are in; an admin any.")
    return r


@router.patch("/relationships/{rel_id}", response_model=RelationshipOut)
def change_relationship(
    rel_id: str,
    body: RelationshipIn,
    request: Request,
    c: Caller = Depends(caller),
    version: int = Depends(if_match),
):
    with server(request).db.tx() as s:
        r = _editable(s, c, rel_id)
        check(r, version, lambda: _rel_out(s, c, r))
        before = (r.relation, r.person1Id, r.person2Id)
        dates = (r.fromDate, r.toDate)
        _apply(s, c, r, body)
        # A marriage changed in any way is confirmed again by the other (S10.10.4).
        changed = before != (r.relation, r.person1Id, r.person2Id) or dates != (
            r.fromDate,
            r.toDate,
        )
        people.confirm(s, c.id, r, fresh=changed)
        r.updatedAt = clock.now()
        s.flush()
        _rewash(s, before, (r.relation, r.person1Id, r.person2Id))
        return _rel_out(s, c, r)


@router.post("/relationships/{rel_id}/confirm", response_model=RelationshipOut)
def confirm_relationship(rel_id: str, request: Request, c: Caller = Depends(caller)):
    """A spouse confirms the marriage from their own Profile, or an admin for a person who
    isn't a user (S10.10.4); once both have, it counts for wash sales and tax books."""
    with server(request).db.tx() as s:
        r = s.get(Relationship, rel_id)
        if r is None or r.deleted:
            raise Problem(404, "not-found", "Not found")
        for i in (r.person1Id, r.person2Id):
            people.get(s, c.id, i)
        if r.relation != "spouse":
            raise Problem(409, "not-a-marriage", "Only a marriage is confirmed.")
        if not people.confirm(s, c.id, r):
            raise Problem(403, "not-yours-to-confirm", "Only the other spouse confirms this.")
        r.updatedAt = clock.now()
        s.flush()
        _rewash(s, (r.relation, r.person1Id, r.person2Id))
        activity.record(s, "relationship.confirmed", actor=c.id, owner=c.id)
        return _rel_out(s, c, r)


@router.delete("/relationships/{rel_id}", response_model=Deleted[None])
def delete_relationship(
    rel_id: str, request: Request, c: Caller = Depends(caller), version: int = Depends(if_match)
):
    with server(request).db.tx() as s:
        r = _editable(s, c, rel_id)
        check(r, version, lambda: _rel_out(s, c, r))
        r.mark_deleted(c.id)
        s.flush()
        _rewash(s, (r.relation, r.person1Id, r.person2Id))
        return Deleted[None](deleted=gone(r))
