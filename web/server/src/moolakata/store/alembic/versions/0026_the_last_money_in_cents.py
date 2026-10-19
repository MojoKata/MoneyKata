"""The last money columns in integer cents, as all money is (requirements S14.3): a budget
line's amount, a qualified education expense's and an estimated tax payment's, until now
decimal text.

Revision: 0026
Follows: 0025
"""

from decimal import ROUND_HALF_EVEN, Decimal

from alembic import op

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None

AMOUNT = ("\tamount TEXT NOT NULL, \n", "\tamount INTEGER NOT NULL, \n")
TABLES = ("BudgetLine", "QualifiedExpense", "EstimatedPayment")


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
    for name in TABLES:
        # Each amount written as its whole number of cents first, so the copy keeps it exactly.
        rows = conn.exec_driver_sql(f'SELECT id, amount FROM "{name}"').fetchall()  # noqa: S608
        for row_id, amount in rows:
            cents = Decimal(amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN) * 100
            conn.exec_driver_sql(
                f'UPDATE "{name}" SET amount = ? WHERE id = ?',  # noqa: S608
                (str(int(cents)), row_id),
            )
        rebuild(conn, name, [AMOUNT])


def downgrade() -> None:
    raise NotImplementedError("MoolaKata migrates forward only; restore a backup to go back")
