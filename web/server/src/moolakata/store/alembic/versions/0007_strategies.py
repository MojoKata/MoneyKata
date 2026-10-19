"""Strategies (requirements S3.5): legs held together and shown as one, and the proposals
turned down.

Revision: 0007
Follows: 0006
"""

import sqlalchemy as sa
from alembic import op

import moolakata.store.types

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "Strategy",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("accountId", sa.Text(), nullable=False),
        sa.Column("underlyingId", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("openedOn", moolakata.store.types.Day(), nullable=False),
        sa.Column("cashSecured", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.Column("marginRequirement", moolakata.store.types.Cents(), nullable=True),
        sa.Column("dismissed", sa.Boolean(), server_default=sa.text("0"), nullable=False),
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
        sa.CheckConstraint("id GLOB 'Strat_*' AND length(id) = 32", name=op.f("ck_Strategy_id")),
        sa.CheckConstraint(
            '"deletedAt" IS NOT NULL OR "deletedById" IS NULL', name=op.f("ck_Strategy_deleted_by")
        ),
        sa.ForeignKeyConstraint(
            ["accountId"],
            ["Account.id"],
            name=op.f("fk_Strategy_accountId_Account"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["deletedById"], ["User.id"], name=op.f("fk_Strategy_deletedById_User")
        ),
        sa.ForeignKeyConstraint(
            ["underlyingId"], ["Instrument.id"], name=op.f("fk_Strategy_underlyingId_Instrument")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_Strategy")),
        info={"prefix": "Strat", "softDelete": True},
        sqlite_with_rowid=False,
    )
    with op.batch_alter_table("Strategy", schema=None) as batch_op:
        batch_op.create_index("ix_Strategy_accountId", ["accountId"], unique=False)

    op.create_table(
        "StrategyLegs",
        sa.Column("strategyId", sa.Text(), nullable=False),
        sa.Column("instrumentId", sa.Text(), nullable=False),
        sa.Column("quantity", moolakata.store.types.Dec(), nullable=True),
        sa.Column("addedOn", moolakata.store.types.Day(), nullable=False),
        sa.Column(
            "deleted",
            sa.Boolean(),
            sa.Computed('"deletedAt" IS NOT NULL', persisted=False),
            nullable=True,
        ),
        sa.Column("deletedAt", moolakata.store.types.UtcTimestamp(), nullable=True),
        sa.Column("deletedById", sa.Text(), nullable=True),
        sa.Column("createdAt", moolakata.store.types.UtcTimestamp(), nullable=False),
        sa.CheckConstraint(
            '"deletedAt" IS NOT NULL OR "deletedById" IS NULL',
            name=op.f("ck_StrategyLegs_deleted_by"),
        ),
        sa.ForeignKeyConstraint(
            ["deletedById"], ["User.id"], name=op.f("fk_StrategyLegs_deletedById_User")
        ),
        sa.ForeignKeyConstraint(
            ["instrumentId"],
            ["Instrument.id"],
            name=op.f("fk_StrategyLegs_instrumentId_Instrument"),
        ),
        sa.ForeignKeyConstraint(
            ["strategyId"],
            ["Strategy.id"],
            name=op.f("fk_StrategyLegs_strategyId_Strategy"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("strategyId", "instrumentId", name=op.f("pk_StrategyLegs")),
        info={"softDelete": True, "pairs": True},
    )


def downgrade() -> None:
    raise NotImplementedError("MoolaKata migrates forward only; restore a backup to go back")
