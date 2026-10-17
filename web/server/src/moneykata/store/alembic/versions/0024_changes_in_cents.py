"""An edit's change to the realized gains is money, kept in integer cents as all money is
(requirements S14.3): the column 0023 made as decimal text becomes cents.

Revision: 0024
Follows: 0023
"""

from decimal import ROUND_HALF_EVEN, Decimal

from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


GAINS = ("\tgains TEXT NOT NULL, \n", "\tgains INTEGER NOT NULL, \n")


def rebuild(conn, name: str, edits: list[tuple[str, str]]) -> None:
    sql = conn.exec_driver_sql(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)
    ).scalar_one()
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
    # Each change written as its whole number of cents first, so the copy keeps it exactly.
    for change_id, gains in conn.exec_driver_sql(
        'SELECT id, gains FROM "TaxBookChange"'
    ).fetchall():
        cents = Decimal(gains).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN) * 100
        conn.exec_driver_sql(
            'UPDATE "TaxBookChange" SET gains = ? WHERE id = ?', (str(int(cents)), change_id)
        )
    rebuild(conn, "TaxBookChange", [GAINS])


def downgrade() -> None:
    raise NotImplementedError("MoneyKata migrates forward only; restore a backup to go back")
