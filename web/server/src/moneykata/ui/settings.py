"""Settings, for admins (requirements §19). Each section of the screen reads and writes its
own keys; secrets and the sources come with their sections' routes."""

from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select

from .. import activity, settings, timezones
from ..errors import FieldError, Problem
from ..store.entities.core import Setting
from .conventions import Model
from .deps import Caller, admin, server

router = APIRouter(prefix="/ui/api", tags=["settings"])


class SettingsView(Model):
    values: dict[str, Any]
    sections: dict[str, list[str]]
    serverZone: str
    versions: dict[str, int]


def view(s) -> SettingsView:
    values = {k: settings.get(s, k) for k in settings.DEFINITIONS}
    sections: dict[str, list[str]] = {}
    for k, d in settings.DEFINITIONS.items():
        sections.setdefault(d.section, []).append(k)
    versions = {r.key: r.version for r in s.scalars(select(Setting))}
    return SettingsView(
        values=values, sections=sections, serverZone=timezones.host_zone(), versions=versions
    )


@router.get("/settings", response_model=SettingsView)
def get_settings(request: Request, c: Caller = Depends(admin)):
    with server(request).db.read() as s:
        return view(s)


@router.patch("/settings", response_model=SettingsView)
def change_settings(body: dict[str, Any], request: Request, c: Caller = Depends(admin)):
    """Every key is checked before any is saved; a refusal names each field (§3.7)."""
    errors: list[FieldError] = []
    clean = {}
    for key, value in body.items():
        try:
            clean[key] = settings.coerce(key, value)
        except Problem as p:
            errors += p.errors
    if errors:
        raise Problem(422, errors[0].code, errors[0].message, errors)
    with server(request).db.tx() as s:
        changed = [k for k, v in clean.items() if settings.get(s, k) != v]
        for k in changed:
            settings.put(s, k, clean[k], c.id)
        if changed:
            activity.record(
                s,
                "settings.changed",
                actor=c.id,
                for_admins=True,
                detail={"fields": sorted(changed)},
            )
        s.flush()
        return view(s)
