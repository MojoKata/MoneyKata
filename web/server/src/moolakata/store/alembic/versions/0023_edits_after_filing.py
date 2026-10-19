"""Edits after filing (requirements S2.8.3, S8.15): an edit made anyway to a year whose federal
return was filed is kept on each tax book that closed the year, with how much it moved the
realized gains, until an amended federal return or No amendment needed settles it.

Revision: 0023
Follows: 0022
"""

import sqlalchemy as sa
from alembic import op

import moolakata.store.types

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "TaxBookChange",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("bookId", sa.Text(), nullable=False),
        sa.Column("accountId", sa.Text(), nullable=False),
        sa.Column("gains", moolakata.store.types.Dec(), nullable=False),
        sa.Column("madeById", sa.Text(), nullable=True),
        sa.Column("settled", sa.Text(), nullable=True),
        sa.Column("settledAt", moolakata.store.types.UtcTimestamp(), nullable=True),
        sa.Column("settledById", sa.Text(), nullable=True),
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
            "id GLOB 'TxChg_*' AND length(id) = 32", name=op.f("ck_TaxBookChange_id")
        ),
        sa.CheckConstraint(
            "settled IS NULL OR settled IN ('amended', 'not-needed')",
            name=op.f("ck_TaxBookChange_settled"),
        ),
        sa.CheckConstraint(
            '"deletedAt" IS NOT NULL OR "deletedById" IS NULL',
            name=op.f("ck_TaxBookChange_deleted_by"),
        ),
        sa.CheckConstraint(
            '(settled IS NULL) = ("settledAt" IS NULL)', name=op.f("ck_TaxBookChange_settled_at")
        ),
        sa.ForeignKeyConstraint(
            ["accountId"],
            ["Account.id"],
            name=op.f("fk_TaxBookChange_accountId_Account"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["bookId"],
            ["TaxBook.id"],
            name=op.f("fk_TaxBookChange_bookId_TaxBook"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["deletedById"], ["User.id"], name=op.f("fk_TaxBookChange_deletedById_User")
        ),
        sa.ForeignKeyConstraint(
            ["madeById"], ["User.id"], name=op.f("fk_TaxBookChange_madeById_User")
        ),
        sa.ForeignKeyConstraint(
            ["settledById"], ["User.id"], name=op.f("fk_TaxBookChange_settledById_User")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_TaxBookChange")),
        info={"prefix": "TxChg", "softDelete": True},
        sqlite_with_rowid=False,
    )
    with op.batch_alter_table("TaxBookChange", schema=None) as batch_op:
        batch_op.create_index("ix_TaxBookChange_bookId", ["bookId"], unique=False)


def downgrade() -> None:
    raise NotImplementedError("MoolaKata migrates forward only; restore a backup to go back")
