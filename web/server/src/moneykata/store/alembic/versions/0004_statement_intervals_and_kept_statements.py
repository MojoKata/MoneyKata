"""Statements expected and statements kept without reading (requirements S1.11.7, S1.3.3.6):
an account's statement interval and the learned one its owner dismissed, and `kept` among an
import's formats.

SQLite can't add a CHECK to a table in place, so `Account` and `Import` are rebuilt as 0002
rebuilds tables: the new table made from the old one's SQL with the clauses added, the rows
copied, the old table dropped, the new one renamed, its indexes made again. Migrations run with
foreign keys off and the Effective views dropped (store/migrate.py).

Revision: 0004
Follows: 0003
"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

INTERVAL_COLUMNS = (
    '"openingDate" TEXT, \n',
    '"openingDate" TEXT, \n\t"statementInterval" TEXT, \n\t"statementIntervalDismissed" TEXT, \n',
)
INTERVAL_CHECK = (
    'CONSTRAINT "ck_Account_mask" CHECK (mask IS NULL OR (length(mask) = 4 AND mask GLOB '
    "'[0-9]*')), \n",
    'CONSTRAINT "ck_Account_mask" CHECK (mask IS NULL OR (length(mask) = 4 AND mask GLOB '
    '\'[0-9]*\')), \n\tCONSTRAINT "ck_Account_statement_interval" CHECK ("statementInterval" '
    "IS NULL OR \"statementInterval\" IN ('monthly', 'quarterly', 'yearly', 'none')), \n",
)
KEPT_FORMAT = (
    "CHECK (\"format\" IN ('ofx', 'csv', 'statement'))",
    "CHECK (\"format\" IN ('ofx', 'csv', 'statement', 'kept'))",
)


def rebuild(conn, name: str, edits: list[tuple[str, str]]) -> None:
    sql = conn.exec_driver_sql(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)
    ).scalar_one()
    # The stored columns: a generated one (hidden 2 or 3) is made again by the new table.
    stored = [
        r[1] for r in conn.exec_driver_sql(f'PRAGMA table_xinfo("{name}")').fetchall() if r[6] == 0
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
    rebuild(conn, "Account", [INTERVAL_COLUMNS, INTERVAL_CHECK])
    rebuild(conn, "Import", [KEPT_FORMAT])


def downgrade() -> None:
    raise NotImplementedError("MoneyKata migrates forward only; restore a backup to go back")
