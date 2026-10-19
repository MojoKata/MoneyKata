"""Bitcoin, the rest (requirements S1.6, S1.7.1, S8.19): bitcoin transfers between the owner's
accounts proposed as pairs (`TransferMatch`), a transaction no longer on the chain, each user's
BTC or sats, a tax book's reading of network fees, and descriptors among a wallet's keys.

`TaxBook`, `Transaction`, `User` and `WalletKey` are rebuilt to add their clauses, as 0004
rebuilds tables.

Revision: 0009
Follows: 0008
"""

import sqlalchemy as sa
from alembic import op

import moolakata.store.types

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


TAX_BOOK = [
    (
        "\tyear INTEGER NOT NULL, \n",
        "\tyear INTEGER NOT NULL, \n\t\"bitcoinFees\" TEXT DEFAULT 'sale' NOT NULL, \n",
    ),
    (
        'CONSTRAINT "pk_TaxBook" PRIMARY KEY (id), \n',
        'CONSTRAINT "pk_TaxBook" PRIMARY KEY (id), \n\tCONSTRAINT "ck_TaxBook_bitcoin_fees" '
        "CHECK (\"bitcoinFees\" IN ('sale', 'not-taxed')), \n",
    ),
]
TRANSACTION = [('\t"createdById" TEXT, \n', '\t"createdById" TEXT, \n\t"offChainAt" TEXT, \n')]
USER = [
    (
        "\t\"alertEmails\" TEXT DEFAULT 'daily' NOT NULL, \n",
        "\t\"alertEmails\" TEXT DEFAULT 'daily' NOT NULL, \n\t\"bitcoinUnit\" TEXT DEFAULT 'btc' NOT NULL, \n",
    ),
    (
        "CONSTRAINT \"ck_User_alert_emails\" CHECK (\"alertEmails\" IN ('each', 'daily', 'none')), \n",
        "CONSTRAINT \"ck_User_alert_emails\" CHECK (\"alertEmails\" IN ('each', 'daily', 'none')), \n"
        "\tCONSTRAINT \"ck_User_bitcoin_unit\" CHECK (\"bitcoinUnit\" IN ('btc', 'sats')), \n",
    ),
]
WALLET_KEY = [
    ("CHECK (kind IN ('xpub', 'address'))", "CHECK (kind IN ('xpub', 'descriptor', 'address'))")
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
    op.create_table(
        "TransferMatch",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("ownerId", sa.Text(), nullable=False),
        sa.Column("outId", sa.Text(), nullable=False),
        sa.Column("inId", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), server_default=sa.text("'proposed'"), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("createdAt", moolakata.store.types.UtcTimestamp(), nullable=False),
        sa.Column("updatedAt", moolakata.store.types.UtcTimestamp(), nullable=False),
        sa.Column(
            "deleted",
            sa.Boolean(),
            sa.Computed('"deletedAt" IS NOT NULL', persisted=False),
            nullable=True,
        ),
        sa.Column("deletedAt", moolakata.store.types.UtcTimestamp(), nullable=True),
        sa.Column("deletedById", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "id GLOB 'XfrMt_*' AND length(id) = 32", name=op.f("ck_TransferMatch_id")
        ),
        sa.CheckConstraint(
            '"deletedAt" IS NOT NULL OR "deletedById" IS NULL',
            name=op.f("ck_TransferMatch_deleted_by"),
        ),
        sa.CheckConstraint(
            "\"state\" IN ('proposed', 'confirmed', 'rejected')",
            name=op.f("ck_TransferMatch_state"),
        ),
        sa.ForeignKeyConstraint(
            ["deletedById"], ["User.id"], name=op.f("fk_TransferMatch_deletedById_User")
        ),
        sa.ForeignKeyConstraint(
            ["inId"],
            ["Transaction.id"],
            name=op.f("fk_TransferMatch_inId_Transaction"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["outId"],
            ["Transaction.id"],
            name=op.f("fk_TransferMatch_outId_Transaction"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["ownerId"], ["User.id"], name=op.f("fk_TransferMatch_ownerId_User")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_TransferMatch")),
        info={"prefix": "XfrMt", "softDelete": True},
        sqlite_with_rowid=False,
    )
    with op.batch_alter_table("TransferMatch", schema=None) as batch_op:
        batch_op.create_index("ix_TransferMatch_owner", ["ownerId", "state"], unique=False)
        batch_op.create_index(
            "ux_TransferMatch_outId_inId",
            ["outId", "inId"],
            unique=True,
            sqlite_where=sa.text("NOT deleted"),
        )

    conn = op.get_bind()
    rebuild(conn, "TaxBook", TAX_BOOK)
    rebuild(conn, "Transaction", TRANSACTION)
    rebuild(conn, "User", USER)
    rebuild(conn, "WalletKey", WALLET_KEY)


def downgrade() -> None:
    raise NotImplementedError("MoolaKata migrates forward only; restore a backup to go back")
