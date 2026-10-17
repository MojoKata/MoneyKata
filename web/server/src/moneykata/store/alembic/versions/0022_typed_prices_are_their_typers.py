"""Typed prices are their typers' (requirements S4.10): a price a user types values their own
accounts, never another user's, so typed prices leave the shared closes for a table of their
own, keyed by who typed them. A typed price kept before names its typer; one that names nobody
stays where it was.

Revision: 0022
Follows: 0021
"""

import sqlalchemy as sa
from alembic import op

import moneykata.store.types

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "TypedPrice",
        sa.Column("instrumentId", sa.Text(), nullable=False),
        sa.Column("userId", sa.Text(), nullable=False),
        sa.Column("date", moneykata.store.types.Day(), nullable=False),
        sa.Column("close", moneykata.store.types.Dec(), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
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
            '"deletedAt" IS NOT NULL OR "deletedById" IS NULL',
            name=op.f("ck_TypedPrice_deleted_by"),
        ),
        sa.ForeignKeyConstraint(
            ["deletedById"], ["User.id"], name=op.f("fk_TypedPrice_deletedById_User")
        ),
        sa.ForeignKeyConstraint(
            ["instrumentId"], ["Instrument.id"], name=op.f("fk_TypedPrice_instrumentId_Instrument")
        ),
        sa.ForeignKeyConstraint(["userId"], ["User.id"], name=op.f("fk_TypedPrice_userId_User")),
        sa.PrimaryKeyConstraint("instrumentId", "userId", "date", name=op.f("pk_TypedPrice")),
        info={"softDelete": True},
    )
    with op.batch_alter_table("TypedPrice", schema=None) as batch_op:
        batch_op.create_index(
            "ix_TypedPrice_user", ["userId", "instrumentId", "date"], unique=False
        )
    conn = op.get_bind()
    conn.exec_driver_sql(
        'INSERT INTO "TypedPrice" ("instrumentId", "userId", date, close, version, "updatedAt", '
        '"deletedAt", "deletedById") SELECT "instrumentId", "enteredById", date, close, version, '
        '"updatedAt", "deletedAt", "deletedById" FROM "Price" '
        "WHERE source = 'manual' AND \"enteredById\" IS NOT NULL"
    )
    conn.exec_driver_sql(
        'DELETE FROM "Price" WHERE source = \'manual\' AND "enteredById" IS NOT NULL'
    )


def downgrade() -> None:
    raise NotImplementedError("MoneyKata migrates forward only; restore a backup to go back")
