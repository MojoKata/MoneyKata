"""The connector, trusted with care (requirements S18.4.5, S18.5.4): an address it reported
from that no admin has accepted is kept apart from the last one, and its identity key's
signature over its sealing key is kept for browsers to check before they seal to it.

Revision: 0020
Follows: 0019
"""

from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


CONNECTOR = (
    "\tprotocol INTEGER, \n",
    '\tprotocol INTEGER, \n\t"newAddress" TEXT, \n\t"sealingSignature" TEXT, \n',
)


def rebuild(conn, name: str, edits: list[tuple[str, str]], drop: tuple[str, ...] = ()) -> None:
    sql = conn.exec_driver_sql(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)
    ).scalar_one()
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
    conn = op.get_bind()
    rebuild(conn, "Connector", [CONNECTOR])
    # An address reported and not yet accepted is the one kept apart.
    conn.exec_driver_sql(
        'UPDATE "Connector" SET "newAddress" = "lastAddress" WHERE "lastAddress" IS NOT NULL '
        'AND "knownAddress" IS NOT NULL AND "lastAddress" != "knownAddress"'
    )


def downgrade() -> None:
    rebuild(
        op.get_bind(),
        "Connector",
        [(CONNECTOR[1], CONNECTOR[0])],
        drop=("newAddress", "sealingSignature"),
    )
