"""Profile › Connections (requirements S18.6, S18.7): a user's own sign-ins at institutions,
kept by the MoneyKata Connector. MoneyKata holds each Connection's record and, while the
connector hasn't collected it, a credential sealed in the browser that MoneyKata can't open;
never a credential itself. The connector's public keys are what any user needs to start one."""

import json

from fastapi import APIRouter, Depends, Request
from pydantic import Field
from sqlalchemy import false, select

from .. import activity, clock, ids
from ..connector import manage, sealed
from ..errors import FieldError, Problem, refuse
from ..links import keys
from ..store.entities.accounts import Account
from ..store.entities.connector import Connection
from .connector import ConnectionOut, connection_out
from .conventions import Deleted, ExactRoute, Model, check, gone, if_match
from .deps import Caller, caller, server

router = APIRouter(prefix="/ui/api", route_class=ExactRoute, tags=["connections"])

# A watched folder was weighed and turned down (rejected ideas, S18.9): a Connection made
# before keeps the name `folder` in its row, as history, and is never made again.
DRIVERS = ("ofx-direct", "schwab")
# What each driver's settings hold (docs/connector-protocol.md §6), checked here so the
# connector gets what it expects. Values are text the owner typed; none is a credential.
SETTINGS = {
    "ofx-direct": {
        "url": str,
        "org": str,
        "fid": str,
        "accountType": str,
        "accountId": str,
        "bankId": None,  # the routing number, for bank accounts
    },
    "schwab": {"appKey": str},
}

# The setting that names the institution's server, for the drivers that have one.
ADDRESS = {"ofx-direct": "url"}


class ConnectorInfo(Model):
    """What any user needs to start a Connection: whether a connector is paired, and its keys."""

    paired: bool
    confirmed: bool  # an admin compared the fingerprints (S18.4.3); sealing waits for it
    locked: bool
    fingerprint: str | None  # four groups of four
    sealingKey: str | None  # base64url, for sealing in the browser (S18.7.1)
    # The connector's identity key and its signature over the sealing key: the browser checks
    # the one against the other before sealing (S18.4.5).
    identityKey: str | None = None
    sealingSignature: str | None = None


class NewConnection(Model):
    driver: str
    label: str
    settings: dict = Field(default_factory=dict)


class ConnectionChange(Model):
    label: str | None = None
    settings: dict | None = None


class Credential(Model):
    """A credential sealed in the browser to the connector's sealing key: the box as it is."""

    sealed: str


class ConnectionMade(Model):
    connection: ConnectionOut
    command: str  # for the stricter way: typed on the connector's host (S18.7.2)


def _info(s) -> ConnectorInfo:
    row = manage.paired(s)
    if row is None:
        return ConnectorInfo(
            paired=False, confirmed=False, locked=True, fingerprint=None, sealingKey=None
        )
    return ConnectorInfo(
        paired=True,
        confirmed=row.confirmedAt is not None,
        locked=row.locked,
        fingerprint=keys.short(keys.fingerprint(keys.unb64(row.identityKey))),
        sealingKey=row.sealingKey,
        identityKey=row.identityKey,
        sealingSignature=row.sealingSignature,
    )


@router.get("/connector", response_model=ConnectorInfo)
def connector_info(request: Request, c: Caller = Depends(caller)):
    with server(request).db.read() as s:
        return _info(s)


def _check_settings(driver: str, settings: dict) -> dict:
    shape = SETTINGS[driver]
    out = {}
    errors = []
    for key, kind in shape.items():
        v = settings.get(key)
        if kind is None:  # optional text
            if v not in (None, "") and (not isinstance(v, str) or len(v) > 500):
                errors.append(FieldError(f"settings.{key}", "settings-invalid", "Too long."))
            elif isinstance(v, str) and v.strip():
                out[key] = v.strip()
            continue
        if kind is list:
            if v is None:
                v = []
            if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
                errors.append(FieldError(f"settings.{key}", "settings-invalid", "A list of rules."))
                continue
            out[key] = [x.strip() for x in v if x.strip()][:200]
        else:
            if not isinstance(v, str) or not v.strip():
                errors.append(FieldError(f"settings.{key}", "settings-missing", "Needed."))
                continue
            if len(v) > 500:
                errors.append(FieldError(f"settings.{key}", "settings-invalid", "Too long."))
                continue
            out[key] = v.strip()
    if errors:
        raise Problem(422, errors[0].code, errors[0].message, errors)
    return out


def _mine(s, c: Caller, connection_id: str) -> Connection:
    row = s.get(Connection, connection_id)
    if row is None or row.deleted or row.ownerId != c.id or row.state == "removed":
        raise Problem(404, "not-found", "No such connection.")
    return row


@router.get("/profile/connections", response_model=list[ConnectionOut])
def list_connections(request: Request, c: Caller = Depends(caller)):
    with server(request).db.read() as s:
        rows = s.scalars(
            select(Connection)
            .where(
                Connection.ownerId == c.id,
                Connection.deleted == false(),
                Connection.state != "removed",
            )
            .order_by(Connection.createdAt)
        )
        return [connection_out(s, r) for r in rows]


@router.post("/profile/connections", response_model=ConnectionMade, status_code=201)
def new_connection(body: NewConnection, request: Request, c: Caller = Depends(caller)):
    if body.driver not in DRIVERS:
        raise refuse("driver", "driver-invalid", "Schwab or OFX Direct Connect.")
    label = body.label.strip()
    if not 1 <= len(label) <= 60:
        raise refuse("label", "label-invalid", "A name to tell it apart: up to 60 letters.")
    settings = _check_settings(body.driver, body.settings)
    with server(request).db.tx() as s:
        row = manage.paired(s)
        if row is None:
            raise refuse(None, "no-connector", "No MoneyKata Connector is paired.", 409)
        twice = s.scalars(
            select(Connection).where(
                Connection.ownerId == c.id,
                Connection.label == label,
                Connection.deleted == false(),
                Connection.state != "removed",
            )
        ).first()
        if twice is not None:
            raise refuse("label", "label-taken", "You already have a connection with that name.")
        conn = Connection(
            id=ids.new_id("Conn"),
            ownerId=c.id,
            connectorId=row.id,
            driver=body.driver,
            label=label,
            state="new",
            settings=json.dumps(settings, sort_keys=True),
        )
        s.add(conn)
        s.flush()
        activity.record(
            s,
            "connection.created",
            actor=c.id,
            subject_kind="connection",
            subject_id=conn.id,
            owner=c.id,
            detail={"driver": body.driver, "label": label},
        )
        return ConnectionMade(
            connection=connection_out(s, conn),
            command=f"docker compose exec connector moneykata-connector connect {conn.id}",
        )


@router.patch("/profile/connections/{connection_id}", response_model=ConnectionOut)
def change_connection(
    connection_id: str,
    body: ConnectionChange,
    request: Request,
    c: Caller = Depends(caller),
    version: int = Depends(if_match),
):
    with server(request).db.tx() as s:
        row = _mine(s, c, connection_id)
        check(row, version, connection_out(s, row))
        changed = []
        if body.label is not None:
            label = body.label.strip()
            if not 1 <= len(label) <= 60:
                raise refuse("label", "label-invalid", "A name: up to 60 letters.")
            if label != row.label:
                row.label = label
                changed.append("label")
        if body.settings is not None:
            settings = _check_settings(row.driver, body.settings)
            text = json.dumps(settings, sort_keys=True)
            where = ADDRESS.get(row.driver)
            if where and settings.get(where) != json.loads(row.settings or "{}").get(where):
                from .deps import recent_auth

                recent_auth(c)  # where its credentials go: the password again (S13.7.2)
            if text != row.settings:
                row.settings = text
                changed.append("settings")
        if changed:
            activity.record(
                s,
                "connection.updated",
                actor=c.id,
                subject_kind="connection",
                subject_id=row.id,
                owner=c.id,
                detail={"fields": changed},
            )
        s.flush()
        return connection_out(s, row)


@router.put("/profile/connections/{connection_id}/credential", response_model=ConnectionOut)
def put_credential(
    connection_id: str, body: Credential, request: Request, c: Caller = Depends(caller)
):
    """The credential sealed in the browser (S18.7.1): kept as it is until the connector
    collects it on its next report. A secret, replaced outright: no version (S13.8.6). The
    password again (S13.7.2), and only once an admin confirmed the pairing (S18.4.3)."""
    from .deps import recent_auth

    recent_auth(c)
    if not sealed.looks_sealed(body.sealed) or len(body.sealed) > 20000:
        raise refuse("sealed", "sealed-invalid", "Not a sealed credential.")
    with server(request).db.tx() as s:
        paired = manage.paired(s)
        if paired is None or paired.confirmedAt is None:
            raise refuse(
                None,
                "pairing-unconfirmed",
                "An admin must confirm the connector's pairing before a sign-in is sealed.",
                409,
            )
        row = _mine(s, c, connection_id)
        row.sealedCredential = body.sealed
        row.sealedAt = clock.now()
        row.signInAddress = None
        activity.record(
            s,
            "connection.credential",
            actor=c.id,
            subject_kind="connection",
            subject_id=row.id,
            owner=c.id,
        )
        s.flush()
        return connection_out(s, row)


@router.delete("/profile/connections/{connection_id}", response_model=Deleted[None])
def remove_connection(
    connection_id: str,
    request: Request,
    c: Caller = Depends(caller),
    version: int = Depends(if_match),
):
    """Remove (S18.6.4): its accounts' sync turns off, and the connector deletes its
    credentials at its next report."""
    with server(request).db.tx() as s:
        row = _mine(s, c, connection_id)
        check(row, version, connection_out(s, row))
        row.state = "removed"
        row.removedAt = clock.now()
        row.sealedCredential = None
        row.sealedAt = None
        for a in s.scalars(select(Account).where(Account.connectionId == row.id)):
            a.connectionId = None
            a.syncAccount = None
        row.mark_deleted(c.id)
        activity.record(
            s,
            "connection.removed",
            actor=c.id,
            subject_kind="connection",
            subject_id=row.id,
            owner=c.id,
            detail={"label": row.label},
        )
        s.flush()
        return Deleted[None](deleted=gone(row))
