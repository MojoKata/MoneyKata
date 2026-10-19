"""Access between users (requirements S10.10.4, S8.14): a spouse's two confirmations, without
which a marriage counts for gifts only; the filer who added an account to a tax book, which
counts only while they can see it; and a tax book made from last year's, whose copy waits until
every filer has accepted it.

`Relationship`, `TaxBook` and `TaxBookAccounts` are rebuilt, as 0014 rebuilds its tables. A
marriage stored before this revision counts as confirmed by both.

Revision: 0015
Follows: 0014
"""

from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None

RELATIONSHIP = (
    '"toDate" TEXT, \n',
    '"toDate" TEXT, \n\t"confirmed1At" TEXT, \n\t"confirmed2At" TEXT, \n',
)
TAX_BOOK = (
    "\"bitcoinFees\" TEXT DEFAULT 'sale' NOT NULL, \n",
    '"bitcoinFees" TEXT DEFAULT \'sale\' NOT NULL, \n\t"fromLastYear" BOOLEAN DEFAULT 0 NOT NULL, \n',
)
TAX_BOOK_ACCOUNTS = (
    "counted BOOLEAN NOT NULL, \n",
    'counted BOOLEAN NOT NULL, \n\t"addedById" TEXT, \n',
)
ADDED_BY = (
    'CONSTRAINT "fk_TaxBookAccounts_deletedById_User" FOREIGN KEY("deletedById") '
    'REFERENCES "User" (id)',
    'CONSTRAINT "fk_TaxBookAccounts_addedById_User" FOREIGN KEY("addedById") '
    'REFERENCES "User" (id), \n\tCONSTRAINT "fk_TaxBookAccounts_deletedById_User" FOREIGN '
    'KEY("deletedById") REFERENCES "User" (id)',
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
    rebuild(conn, "Relationship", [RELATIONSHIP])
    conn.exec_driver_sql(
        'UPDATE "Relationship" SET "confirmed1At" = "createdAt", "confirmed2At" = "createdAt" '
        "WHERE relation = 'spouse'"
    )
    rebuild(conn, "TaxBook", [TAX_BOOK])
    rebuild(conn, "TaxBookAccounts", [TAX_BOOK_ACCOUNTS, ADDED_BY])


def downgrade() -> None:
    conn = op.get_bind()
    rebuild(
        conn,
        "TaxBookAccounts",
        [(TAX_BOOK_ACCOUNTS[1], TAX_BOOK_ACCOUNTS[0]), (ADDED_BY[1], ADDED_BY[0])],
        drop=("addedById",),
    )
    rebuild(conn, "TaxBook", [(TAX_BOOK[1], TAX_BOOK[0])], drop=("fromLastYear",))
    rebuild(
        conn,
        "Relationship",
        [(RELATIONSHIP[1], RELATIONSHIP[0])],
        drop=("confirmed1At", "confirmed2At"),
    )
