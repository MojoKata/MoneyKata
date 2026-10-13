"""The columns and constraints every table carries (docs/schema.md §2, §4).

A record table has a prefixed id with its CHECK, is WITHOUT ROWID, and carries the
soft-delete fields with their CHECK, plus `version`, `createdAt` and `updatedAt` for the API's
concurrency rule (requirements S13.8.6). Tables removed outright (schema.md §4.4) say so in
`info["exception"]`.
"""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Table,
    Text,
    text,
)

from ..types import UtcTimestamp

NAMING = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
metadata = MetaData(naming_convention=NAMING)


def soft_delete(table: str) -> list:
    return [
        Column("deleted", Boolean, nullable=False, server_default=text("0")),
        Column("deletedAt", UtcTimestamp),
        Column("deletedById", Text, ForeignKey("User.id")),
        CheckConstraint('deleted = ("deletedAt" IS NOT NULL)', name="deleted_at"),
        CheckConstraint('deleted OR "deletedById" IS NULL', name="deleted_by"),
    ]


def record(name: str, prefix: str, *columns, **kw) -> Table:
    """A table of records with a prefixed id (schema.md §2) and soft deletes (§4)."""
    length = len(prefix) + 1 + 26
    return Table(
        name,
        metadata,
        Column("id", Text, primary_key=True),
        *columns,
        Column("version", Integer, nullable=False, server_default=text("1")),
        Column("createdAt", UtcTimestamp, nullable=False),
        Column("updatedAt", UtcTimestamp, nullable=False),
        *soft_delete(name),
        CheckConstraint(f"id GLOB '{prefix}_*' AND length(id) = {length}", name="id"),
        sqlite_with_rowid=False,
        info={"prefix": prefix, "softDelete": True},
        **kw,
    )


def pairs(name: str, *columns, **kw) -> Table:
    """A many-to-many table: plural name, the pair of keys as its primary key (schema.md §1.2)."""
    return Table(
        name,
        metadata,
        *columns,
        *soft_delete(name),
        Column("createdAt", UtcTimestamp, nullable=False),
        info={"softDelete": True, "pairs": True},
        **kw,
    )


def keyed(name: str, *columns, **kw) -> Table:
    """A table keyed by name rather than an id, with soft deletes (Settings)."""
    return Table(
        name,
        metadata,
        *columns,
        Column("version", Integer, nullable=False, server_default=text("1")),
        Column("updatedAt", UtcTimestamp, nullable=False),
        *soft_delete(name),
        info={"softDelete": True},
        **kw,
    )


def exception(name: str, reason: str, *columns, prefix: str | None = None, **kw) -> Table:
    """A table that schema.md §4.4 removes outright, or never deletes from at all."""
    cols = list(columns)
    info = {"softDelete": False, "exception": reason}
    if prefix:
        length = len(prefix) + 1 + 26
        cols.insert(0, Column("id", Text, primary_key=True))
        cols.append(CheckConstraint(f"id GLOB '{prefix}_*' AND length(id) = {length}", name="id"))
        info["prefix"] = prefix
        kw.setdefault("sqlite_with_rowid", False)
    return Table(name, metadata, *cols, info=info, **kw)


def unique_live(table: Table, *columns: str, name: str | None = None) -> Index:
    """Uniqueness that ignores deleted records (schema.md §4.3)."""
    return Index(
        name or f"ux_{table.name}_{'_'.join(columns)}",
        *(table.c[c] for c in columns),
        unique=True,
        sqlite_where=text("NOT deleted"),
    )
