"""File retention and pruning (requirements S14.10): a category's *Keep receipts for*, and a
receipt's *Keep* and when its file was pruned, and by whom.

`Category` and `Receipt` are rebuilt to add their clauses, as 0004 rebuilds tables.

Revision: 0006
Follows: 0005
"""

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

CATEGORY = [
    ('"createdById" TEXT, \n', '"createdById" TEXT, \n\t"keepReceiptsYears" INTEGER, \n'),
    (
        "CONSTRAINT \"ck_Category_kind\" CHECK (\"kind\" IN ('expense', 'income', 'transfer')), \n",
        "CONSTRAINT \"ck_Category_kind\" CHECK (\"kind\" IN ('expense', 'income', 'transfer')), \n"
        '\tCONSTRAINT "ck_Category_keep_receipts_years" CHECK ("keepReceiptsYears" IS NULL OR '
        '"keepReceiptsYears" >= 1), \n',
    ),
]
RECEIPT = [
    (
        "filled TEXT DEFAULT '[]' NOT NULL, \n",
        "filled TEXT DEFAULT '[]' NOT NULL, \n\tkeep BOOLEAN DEFAULT 0 NOT NULL, \n"
        '\t"filePrunedAt" TEXT, \n\t"filePrunedById" TEXT, \n',
    ),
    (
        'CONSTRAINT "fk_Receipt_deletedById_User" FOREIGN KEY("deletedById") REFERENCES "User" '
        "(id), \n",
        'CONSTRAINT "fk_Receipt_deletedById_User" FOREIGN KEY("deletedById") REFERENCES "User" '
        '(id), \n\tCONSTRAINT "fk_Receipt_filePrunedById_User" FOREIGN KEY("filePrunedById") '
        'REFERENCES "User" (id), \n',
    ),
]


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
    rebuild(conn, "Category", CATEGORY)
    rebuild(conn, "Receipt", RECEIPT)


def downgrade() -> None:
    raise NotImplementedError("MoolaKata migrates forward only; restore a backup to go back")
