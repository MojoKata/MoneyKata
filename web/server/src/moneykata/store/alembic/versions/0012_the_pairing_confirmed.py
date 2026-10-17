"""A pairing confirmed by an admin (requirements S18.4.3): who compared the fingerprints and
when; until then the connector gets no sealed credential and posts no file.

`Connector` is rebuilt to add the columns and the foreign key, as 0011 rebuilds `Account`:
SQLite adds no constraint to a table in place, and Alembic's batch copy stumbles on the
generated `deleted` column.

Revision: 0012
Follows: 0011
"""

from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

COLUMNS = (
    '"pairedById" TEXT, \n',
    '"pairedById" TEXT, \n\t"confirmedAt" TEXT, \n\t"confirmedById" TEXT, \n',
)
KEY = (
    'CONSTRAINT "fk_Connector_pairedById_User" FOREIGN KEY("pairedById") REFERENCES "User" (id)\n',
    'CONSTRAINT "fk_Connector_pairedById_User" FOREIGN KEY("pairedById") REFERENCES "User" (id), \n'
    '\tCONSTRAINT "fk_Connector_confirmedById_User" FOREIGN KEY("confirmedById") '
    'REFERENCES "User" (id)\n',
)


def rebuild(conn, name: str, edits: list[tuple[str, str]], drop: tuple[str, ...] = ()) -> None:
    sql = conn.exec_driver_sql(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)
    ).scalar_one()
    # The stored columns: a generated one (hidden 2 or 3) is made again by the new table.
    stored = [
        r[1]
        for r in conn.exec_driver_sql(f'PRAGMA table_xinfo("{name}")').fetchall()
        if r[6] == 0 and r[1] not in drop
    ]
    indexes = conn.exec_driver_sql(
        "SELECT sql FROM sqlite_master WHERE type = 'index' AND tbl_name = ? AND sql IS NOT NULL",
        (name,),
    ).fetchall()
    new = sql
    for old, replacement in edits:
        if new.count(old) != 1:
            raise RuntimeError(f"{name}: unexpected declarations")
        new = new.replace(old, replacement)
    head = f'CREATE TABLE "{name}" ('
    conn.exec_driver_sql(f'CREATE TABLE "_new_{name}" (' + new[len(head) :])
    listed = ", ".join(f'"{c}"' for c in stored)
    # The names come from sqlite_master, not from input.
    conn.exec_driver_sql(f'INSERT INTO "_new_{name}" ({listed}) SELECT {listed} FROM "{name}"')  # noqa: S608
    conn.exec_driver_sql(f'DROP TABLE "{name}"')
    conn.exec_driver_sql(f'ALTER TABLE "_new_{name}" RENAME TO "{name}"')
    for (index_sql,) in indexes:
        conn.exec_driver_sql(index_sql)


def upgrade() -> None:
    rebuild(op.get_bind(), "Connector", [COLUMNS, KEY])


def downgrade() -> None:
    rebuild(
        op.get_bind(),
        "Connector",
        [(COLUMNS[1], COLUMNS[0]), (KEY[1], KEY[0])],
        drop=("confirmedAt", "confirmedById"),
    )
