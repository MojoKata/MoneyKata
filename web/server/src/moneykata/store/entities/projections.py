import datetime as dt
from dataclasses import dataclass

from . import Record, SoftDeleted


@dataclass(kw_only=True, eq=False)
class AssumptionSet(Record):
    id: str
    ownerId: str
    figures: str = "{}"


@dataclass(kw_only=True, eq=False)
class Projection(Record):
    id: str
    ownerId: str
    name: str
    goal: str
    builtOn: str = "{}"
    inputs: str = "{}"
    active: bool = False
    baseline: str | None = None
    baselineAt: dt.datetime | None = None


@dataclass(kw_only=True, eq=False)
class ShownProjection(SoftDeleted):
    userId: str
    projectionId: str
    createdAt: dt.datetime
    deletedAt: dt.datetime | None = None
    deletedById: str | None = None


@dataclass(kw_only=True, eq=False)
class TaxFigure(Record):
    id: str
    year: int
    key: str
    value: str
    changedById: str | None = None
