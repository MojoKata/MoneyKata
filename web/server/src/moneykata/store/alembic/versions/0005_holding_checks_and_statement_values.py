"""Brokerage statements (requirements S1.3.3.8): `HoldingCheck`, the positions a statement
shows on its last day, and `statement-value` among an anchor's sources, for its ending value.

`Anchor` is rebuilt to change its CHECK, as 0004 rebuilds tables.

Revision: 0005
Follows: 0004
"""

import sqlalchemy as sa
from alembic import op

import moneykata.store.types

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

VALUE_SOURCE = (
    "CHECK (\"source\" IN ('running-balance', 'ofx', 'statement', 'typed'))",
    "CHECK (\"source\" IN ('running-balance', 'ofx', 'statement', 'typed', 'statement-value'))",
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
    rebuild(op.get_bind(), "Anchor", [VALUE_SOURCE])
    op.create_table(
        "HoldingCheck",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("accountId", sa.Text(), nullable=False),
        sa.Column("importId", sa.Text(), nullable=True),
        sa.Column("asOf", moneykata.store.types.Day(), nullable=False),
        sa.Column("instrumentId", sa.Text(), nullable=True),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("quantity", moneykata.store.types.Dec(), nullable=True),
        sa.Column("price", moneykata.store.types.Dec(), nullable=True),
        sa.Column("marketValue", moneykata.store.types.Cents(), nullable=True),
        sa.Column("costBasis", moneykata.store.types.Cents(), nullable=True),
        sa.Column("cash", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("createdAt", moneykata.store.types.UtcTimestamp(), nullable=False),
        sa.Column("updatedAt", moneykata.store.types.UtcTimestamp(), nullable=False),
        sa.Column(
            "deleted",
            sa.Boolean(),
            sa.Computed('"deletedAt" IS NOT NULL', persisted=False),
            nullable=True,
        ),
        sa.Column("deletedAt", moneykata.store.types.UtcTimestamp(), nullable=True),
        sa.Column("deletedById", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "id GLOB 'HdChk_*' AND length(id) = 32", name=op.f("ck_HoldingCheck_id")
        ),
        sa.CheckConstraint(
            '"deletedAt" IS NOT NULL OR "deletedById" IS NULL',
            name=op.f("ck_HoldingCheck_deleted_by"),
        ),
        sa.ForeignKeyConstraint(
            ["accountId"],
            ["Account.id"],
            name=op.f("fk_HoldingCheck_accountId_Account"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["deletedById"], ["User.id"], name=op.f("fk_HoldingCheck_deletedById_User")
        ),
        sa.ForeignKeyConstraint(
            ["importId"], ["Import.id"], name=op.f("fk_HoldingCheck_importId_Import")
        ),
        sa.ForeignKeyConstraint(
            ["instrumentId"],
            ["Instrument.id"],
            name=op.f("fk_HoldingCheck_instrumentId_Instrument"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_HoldingCheck")),
        info={"prefix": "HdChk", "softDelete": True},
        sqlite_with_rowid=False,
    )
    with op.batch_alter_table("HoldingCheck", schema=None) as batch_op:
        batch_op.create_index("ix_HoldingCheck_account_asOf", ["accountId", "asOf"], unique=False)


def downgrade() -> None:
    raise NotImplementedError("MoneyKata migrates forward only; restore a backup to go back")
