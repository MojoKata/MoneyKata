"""Prices (requirements S4, S16.6): the header's refresh status, Refresh prices, Settings ›
Prices for admins, typed prices and an instrument's stored closes."""

import datetime as dt
import json

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse, Response
from pydantic import Field
from sqlalchemy import false, select

from .. import access, activity, clock, ids, settings
from ..errors import FieldError, Problem, refuse
from ..prices import SOURCES
from ..prices import refresh as pricing
from ..store.entities.accounts import Instrument, Transaction
from ..store.entities.prices import Price, PriceSource
from ..store.entities.users import User
from ..store.repos import secrets as secret_repo
from .conventions import Model, Quantity, if_match, stale
from .deps import Caller, admin, caller, server

router = APIRouter(prefix="/ui/api", tags=["prices"])


class PriceStatus(Model):
    lastRefresh: dt.datetime | None
    stale: bool
    sources: int
    running: bool


class SourceKind(Model):
    name: str
    label: str
    classes: list[str]
    needsKey: bool
    keyUrl: str | None
    terms: str
    termsChecked: dt.date | None
    attribution: str | None
    fetches: bool


class SecretSet(Model):
    setAt: dt.datetime
    setBy: str | None


class SourceRow(SourceKind):
    id: str
    enabled: bool
    preference: dict[str, int]
    key: SecretSet | None
    lastRunAt: dt.datetime | None
    lastOkAt: dt.datetime | None
    lastError: str | None
    version: int


class SourcesView(Model):
    available: list[SourceKind]
    sources: list[SourceRow]
    refreshTime: str
    refreshZone: str


class NewSource(Model):
    name: str


class SourceChange(Model):
    enabled: bool | None = None
    preference: dict[str, int] | None = None
    apiKey: str | None = Field(None, description="the source's key; null removes it")


class TypedPrice(Model):
    date: dt.date
    price: Quantity


class Close(Model):
    date: dt.date
    close: Quantity
    source: str


def _kind(cls) -> SourceKind:
    return SourceKind(
        name=cls.name,
        label=cls.label,
        classes=sorted(cls.classes),
        needsKey=cls.needs_key,
        keyUrl=cls.key_url,
        terms=cls.terms,
        termsChecked=cls.terms_checked,
        attribution=cls.attribution,
        fetches=cls.fetches,
    )


def _shipped(dev: bool) -> list:
    return [c for c in SOURCES.values() if dev or not c.dev_only]


def _row(s, src: PriceSource) -> SourceRow:
    cls = SOURCES[src.name]
    info = secret_repo.info(s, "PriceSource", src.id, "apiKey")
    key = None
    if info:
        by = s.get(User, info.setById) if info.setById else None
        key = SecretSet(setAt=info.setAt, setBy=by.displayName if by else None)
    return SourceRow(
        **_kind(cls).model_dump(),
        id=src.id,
        enabled=src.enabled,
        preference=json.loads(src.preference or "{}"),
        key=key,
        lastRunAt=src.lastRunAt,
        lastOkAt=src.lastOkAt,
        lastError=src.lastError,
        version=src.version,
    )


def _view(s, dev: bool) -> SourcesView:
    from .. import settings

    rows = s.scalars(
        select(PriceSource).where(PriceSource.deleted == false()).order_by(PriceSource.createdAt)
    ).all()
    return SourcesView(
        available=[_kind(c) for c in _shipped(dev)],
        sources=[_row(s, r) for r in rows if r.name in SOURCES],
        refreshTime=settings.get(s, "priceRefreshTime"),
        refreshZone=settings.get(s, "priceRefreshZone"),
    )


def apply_egress(srv) -> None:
    """Only the hosts of enabled sources, the SMTP server, the bitcoin explorer or node and
    linked servers may be reached (S13.5). The SMTP host, a node and a linked server are ones
    an admin named, so they may be on this machine or the LAN."""
    from ..bitcoin import sync as bitcoin
    from ..links.peers import hosts as link_hosts

    with srv.db.read() as s:
        smtp = [h] if (h := settings.get(s, "smtpHost")) else []
        btc, btc_named = bitcoin.hosts(s)
        peers = link_hosts(s)
        srv.guard.allow(
            pricing.hosts(s, srv.config.dev) + smtp + btc + peers,
            allowed_by_name=smtp + btc_named + peers,
        )


@router.get("/prices/status", response_model=PriceStatus)
def price_status(request: Request, c: Caller = Depends(caller)):
    srv = server(request)
    with srv.db.read() as s:
        st = pricing.status(s, srv.config.dev)
    running = srv.tasks.status().get("prices", {}).get("running", False)
    return PriceStatus(**st, running=running)


@router.post("/prices/refresh", status_code=202)
def refresh_prices(request: Request, c: Caller = Depends(caller)):
    """Refresh prices: the daily task, now (S4.4)."""
    if not server(request).tasks.run_now("prices"):
        raise Problem(503, "not-available", "Prices can't be refreshed right now.")
    return Response(status_code=202)


@router.get("/price-sources", response_model=SourcesView)
def list_sources(request: Request, c: Caller = Depends(admin)):
    srv = server(request)
    with srv.db.read() as s:
        return _view(s, srv.config.dev)


@router.post("/price-sources", response_model=SourcesView, status_code=201)
def add_source(body: NewSource, request: Request, c: Caller = Depends(admin)):
    srv = server(request)
    cls = SOURCES.get(body.name)
    if cls is None or (cls.dev_only and not srv.config.dev):
        raise refuse("name", "source-unknown", "Choose a source MoneyKata ships.")
    with srv.db.tx() as s:
        if s.scalars(
            select(PriceSource).where(PriceSource.name == body.name, PriceSource.deleted == false())
        ).first():
            raise refuse("name", "source-added", f"{cls.label} is already added.", 409)
        taken = {}
        for r in s.scalars(select(PriceSource).where(PriceSource.deleted == false())):
            for k, v in json.loads(r.preference or "{}").items():
                taken[k] = max(taken.get(k, 0), v)
        pref = {k: taken.get(k, 0) + 1 for k in sorted(cls.classes)}
        s.add(
            PriceSource(
                id=ids.new_id("Src"),
                name=body.name,
                enabled=not cls.needs_key,
                preference=json.dumps(pref),
                createdById=c.id,
            )
        )
        activity.record(
            s, "prices.source-added", actor=c.id, for_admins=True, detail={"source": body.name}
        )
        s.flush()
        view = _view(s, srv.config.dev)
    apply_egress(srv)
    return JSONResponse(view.model_dump(mode="json"), status_code=201)


@router.patch("/price-sources/{source_id}", response_model=SourcesView)
def change_source(
    source_id: str,
    body: SourceChange,
    request: Request,
    c: Caller = Depends(admin),
    version: int = Depends(if_match),
):
    srv = server(request)
    sent = body.model_fields_set
    with srv.db.tx() as s:
        src = s.get(PriceSource, source_id)
        if src is None or src.deleted or src.name not in SOURCES:
            raise Problem(404, "not-found", "Not found")
        if src.version != version:
            raise stale(_row(s, src))
        cls = SOURCES[src.name]
        fields = []
        if "apiKey" in sent:
            if not cls.needs_key:
                raise refuse("apiKey", "no-key", f"{cls.label} needs no key.")
            if body.apiKey is None:
                secret_repo.remove(s, "PriceSource", src.id, "apiKey")
                src.enabled = False
            else:
                key = body.apiKey.strip()
                if not 8 <= len(key) <= 200 or any(ch.isspace() for ch in key):
                    raise refuse("apiKey", "key-invalid", "Paste the key as the source gives it.")
                secret_repo.put(s, srv.keys.secrets, "PriceSource", src.id, "apiKey", key, c.id)
            fields.append("apiKey")
        if body.enabled is not None and "enabled" in sent:
            if (
                body.enabled
                and cls.needs_key
                and not secret_repo.info(s, "PriceSource", src.id, "apiKey")
            ):
                raise refuse(
                    "enabled", "key-needed", f"{cls.label} needs its key before it can be enabled."
                )
            src.enabled = body.enabled
            fields.append("enabled")
        if body.preference is not None:
            errors = [
                FieldError(f"preference.{k}", "class-not-served", f"{cls.label} doesn't serve {k}.")
                for k in body.preference
                if k not in cls.classes
            ]
            if errors:
                raise Problem(422, errors[0].code, errors[0].message, errors)
            src.preference = json.dumps({k: int(v) for k, v in body.preference.items()})
            fields.append("preference")
        if fields:
            activity.record(
                s,
                "prices.source-changed",
                actor=c.id,
                for_admins=True,
                detail={"source": src.name, "fields": fields},
            )
        s.flush()
        view = _view(s, srv.config.dev)
    apply_egress(srv)
    return view


@router.delete("/price-sources/{source_id}", status_code=204)
def remove_source(
    source_id: str, request: Request, c: Caller = Depends(admin), version: int = Depends(if_match)
):
    srv = server(request)
    with srv.db.tx() as s:
        src = s.get(PriceSource, source_id)
        if src is None or src.deleted:
            raise Problem(404, "not-found", "Not found")
        if src.version != version:
            raise stale({"id": src.id, "version": src.version})
        secret_repo.remove(s, "PriceSource", src.id, "apiKey")
        src.mark_deleted(c.id)
        activity.record(
            s, "prices.source-removed", actor=c.id, for_admins=True, detail={"source": src.name}
        )
    apply_egress(srv)
    return Response(status_code=204)


def _held_writable(s, user_id: str, instrument_id: str) -> bool:
    """A typed price is for an instrument the user holds in an account they can change."""
    account_ids = set(
        s.scalars(
            select(Transaction.accountId).where(
                Transaction.instrumentId == instrument_id, Transaction.deleted == false()
            )
        )
    )
    return any(
        access.RANK[lvl] >= access.RANK["write"]
        for a, lvl in access.visible_accounts(s, user_id)
        if a.id in account_ids
    )


@router.post("/instruments/{instrument_id}/prices", status_code=201)
def type_price(instrument_id: str, body: TypedPrice, request: Request, c: Caller = Depends(caller)):
    """A price from a statement, or typed, with its date (S4.3)."""
    if body.date > clock.today():
        raise refuse("date", "date-in-future", "A price can't be dated in the future.")
    if body.price < 0:
        raise refuse("price", "price-negative", "A price can't be negative.")
    with server(request).db.tx() as s:
        inst = s.get(Instrument, instrument_id)
        if inst is None or inst.deleted or not _held_writable(s, c.id, inst.id):
            raise Problem(404, "not-found", "Not found")
        row = s.get(Price, (inst.id, body.date))
        if row is None:
            s.add(
                Price(
                    instrumentId=inst.id,
                    date=body.date,
                    close=body.price,
                    source="manual",
                    enteredById=c.id,
                )
            )
        else:
            row.close, row.source, row.enteredById = body.price, "manual", c.id
            row.restore()
    server(request).events.publish("prices", {"instrumentId": instrument_id})
    return Response(status_code=201)


@router.get("/instruments/{instrument_id}/prices", response_model=list[Close])
def closes(
    instrument_id: str,
    request: Request,
    c: Caller = Depends(caller),
    start: dt.date | None = Query(None, alias="from"),
    end: dt.date | None = Query(None, alias="to"),
):
    with server(request).db.read() as s:
        inst = s.get(Instrument, instrument_id)
        if inst is None or inst.deleted:
            raise Problem(404, "not-found", "Not found")
        q = select(Price).where(Price.instrumentId == inst.id, Price.deleted == false())
        if start:
            q = q.where(Price.date >= start)
        if end:
            q = q.where(Price.date <= end)
        return [
            Close(date=p.date, close=p.close, source=p.source)
            for p in s.scalars(q.order_by(Price.date))
        ]
