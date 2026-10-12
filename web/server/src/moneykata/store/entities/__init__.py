"""Plain dataclasses, one per table, that import nothing from SQLAlchemy (requirements §17.1.2).
store/mapping.py maps each onto its table."""

import datetime as dt
from dataclasses import dataclass, field


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


@dataclass(kw_only=True, eq=False)
class Record:
    """What every record carries: its version (§16.8.6), its times, and the soft-delete
    fields (schema.md §4.1)."""

    version: int = 1
    createdAt: dt.datetime = field(default_factory=_now)
    updatedAt: dt.datetime = field(default_factory=_now)
    deleted: bool = False
    deletedAt: dt.datetime | None = None
    deletedById: str | None = None

    def mark_deleted(self, by: str | None, at: dt.datetime | None = None) -> None:
        self.deleted = True
        self.deletedAt = at or _now()
        self.deletedById = by

    def restore(self) -> None:
        self.deleted = False
        self.deletedAt = None
        self.deletedById = None
