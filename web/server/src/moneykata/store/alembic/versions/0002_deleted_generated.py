"""`deleted` generated from `deletedAt` (docs/schema.md §4.1): every soft-deleting table is
rebuilt with `deleted` as a virtual generated column, which drops the CHECK that kept the two
in step and states the deleted-by CHECK through `deletedAt`.

SQLite can't turn a stored column into a generated one in place, so each table is rebuilt the
way SQLite documents: the new table made from the old one's SQL, the rows copied, the old table
dropped, the new one renamed, its indexes made again. Migrations run with foreign keys off and
the Effective views dropped (store/migrate.py).

Revision: 0002
Follows: 0001
"""

import re

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

OLD_COLUMN = re.compile(r"\bdeleted BOOLEAN DEFAULT \(?'?0'?\)? NOT NULL")
NEW_COLUMN = 'deleted BOOLEAN GENERATED ALWAYS AS ("deletedAt" IS NOT NULL) VIRTUAL'
# The clause with the comma before it, so it goes cleanly wherever it stands in the list.
OLD_AT = re.compile(
    r',\s*CONSTRAINT "[^"]+_deleted_at" CHECK \(deleted = \("deletedAt" IS NOT NULL\)\)'
)
OLD_BY = 'CHECK (deleted OR "deletedById" IS NULL)'
NEW_BY = 'CHECK ("deletedAt" IS NOT NULL OR "deletedById" IS NULL)'


def rebuilt_sql(name: str, sql: str) -> str:
    """The table's CREATE statement under a temporary name, with the generated column."""
    out, columns = OLD_COLUMN.subn(NEW_COLUMN, sql)
    out, checks = OLD_AT.subn("", out)
    head = f'CREATE TABLE "{name}" ('
    if columns != 1 or checks != 1 or out.count(OLD_BY) != 1 or not out.startswith(head):
        raise RuntimeError(f"{name}: unexpected soft-delete declarations")
    out = out.replace(OLD_BY, NEW_BY)
    return f'CREATE TABLE "_new_{name}" (' + out[len(head) :]


def upgrade() -> None:
    conn = op.get_bind()
    tables = conn.exec_driver_sql(
        "SELECT name, sql FROM sqlite_master WHERE type = 'table' AND sql LIKE ?",
        ("%deleted BOOLEAN DEFAULT%",),
    ).fetchall()
    for name, sql in tables:
        indexes = conn.exec_driver_sql(
            "SELECT sql FROM sqlite_master WHERE type = 'index' AND tbl_name = ? "
            "AND sql IS NOT NULL",
            (name,),
        ).fetchall()
        columns = [
            r[1]
            for r in conn.exec_driver_sql(f'PRAGMA table_info("{name}")').fetchall()
            if r[1] != "deleted"
        ]
        listed = ", ".join(f'"{c}"' for c in columns)
        conn.exec_driver_sql(rebuilt_sql(name, sql))
        # The names come from sqlite_master, not from input.
        copy = f'INSERT INTO "_new_{name}" ({listed}) SELECT {listed} FROM "{name}"'  # noqa: S608
        conn.exec_driver_sql(copy)
        conn.exec_driver_sql(f'DROP TABLE "{name}"')
        conn.exec_driver_sql(f'ALTER TABLE "_new_{name}" RENAME TO "{name}"')
        for (index_sql,) in indexes:
            conn.exec_driver_sql(index_sql)


def downgrade() -> None:
    raise NotImplementedError("MoneyKata migrates forward only; restore a backup to go back")
