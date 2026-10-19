"""Addresses (requirements S10.1.9, S18.2.4.4): a user's recent sign-in addresses and each
session's, so a sign-in from a new address is noticed; the connector's last and accepted
addresses, so a report from somewhere new alerts admins.

`User`, `Session` and `Connector` are rebuilt, as 0012 rebuilds `Connector`.

Revision: 0014
Follows: 0013
"""

from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None

USER = (
    '"totpLastStep" INTEGER, \n',
    '"totpLastStep" INTEGER, \n\t"recentAddresses" TEXT DEFAULT \'{}\' NOT NULL, \n',
)
SESSION = ('"authAt" TEXT NOT NULL, \n', '"authAt" TEXT NOT NULL, \n\taddress TEXT, \n')
CONNECTOR = (
    '"connectorVersion" TEXT, \n',
    '"connectorVersion" TEXT, \n\t"lastAddress" TEXT, \n\t"knownAddress" TEXT, \n',
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
    rebuild(conn, "User", [USER])
    rebuild(conn, "Session", [SESSION])
    rebuild(conn, "Connector", [CONNECTOR])


def downgrade() -> None:
    conn = op.get_bind()
    rebuild(conn, "Connector", [(CONNECTOR[1], CONNECTOR[0])], drop=("lastAddress", "knownAddress"))
    rebuild(conn, "Session", [(SESSION[1], SESSION[0])], drop=("address",))
    rebuild(conn, "User", [(USER[1], USER[0])], drop=("recentAddresses",))
