"""Tax-book dependents (requirements S8.14.5): the people a book's filers claim, and the
counted accounts in a dependent's name.

Revision: 0003
Follows: 0002
"""

import sqlalchemy as sa
from alembic import op

import moneykata.store.types

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "TaxBookDependent",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("bookId", sa.Text(), nullable=False),
        sa.Column("personId", sa.Text(), nullable=False),
        sa.Column("claimedAs", sa.Text(), nullable=False),
        sa.Column("months", sa.Integer(), server_default=sa.text("12"), nullable=False),
        sa.Column("student", sa.Boolean(), server_default=sa.text("0"), nullable=False),
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
            "id GLOB 'TxDep_*' AND length(id) = 32", name=op.f("ck_TaxBookDependent_id")
        ),
        sa.CheckConstraint(
            "\"claimedAs\" IN ('qualifying child', 'qualifying relative')",
            name=op.f("ck_TaxBookDependent_claimed_as"),
        ),
        sa.CheckConstraint(
            '"deletedAt" IS NOT NULL OR "deletedById" IS NULL',
            name=op.f("ck_TaxBookDependent_deleted_by"),
        ),
        sa.CheckConstraint("months BETWEEN 0 AND 12", name=op.f("ck_TaxBookDependent_months")),
        sa.ForeignKeyConstraint(
            ["bookId"],
            ["TaxBook.id"],
            name=op.f("fk_TaxBookDependent_bookId_TaxBook"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["deletedById"], ["User.id"], name=op.f("fk_TaxBookDependent_deletedById_User")
        ),
        sa.ForeignKeyConstraint(
            ["personId"], ["Person.id"], name=op.f("fk_TaxBookDependent_personId_Person")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_TaxBookDependent")),
        info={"prefix": "TxDep", "softDelete": True},
        sqlite_with_rowid=False,
    )
    with op.batch_alter_table("TaxBookDependent", schema=None) as batch_op:
        batch_op.create_index("ix_TaxBookDependent_bookId", ["bookId"], unique=False)
        batch_op.create_index(
            "ux_TaxBookDependent_bookId_personId",
            ["bookId", "personId"],
            unique=True,
            sqlite_where=sa.text("NOT deleted"),
        )

    op.create_table(
        "TaxDependentAccounts",
        sa.Column("dependentId", sa.Text(), nullable=False),
        sa.Column("accountId", sa.Text(), nullable=False),
        sa.Column(
            "deleted",
            sa.Boolean(),
            sa.Computed('"deletedAt" IS NOT NULL', persisted=False),
            nullable=True,
        ),
        sa.Column("deletedAt", moneykata.store.types.UtcTimestamp(), nullable=True),
        sa.Column("deletedById", sa.Text(), nullable=True),
        sa.Column("createdAt", moneykata.store.types.UtcTimestamp(), nullable=False),
        sa.CheckConstraint(
            '"deletedAt" IS NOT NULL OR "deletedById" IS NULL',
            name=op.f("ck_TaxDependentAccounts_deleted_by"),
        ),
        sa.ForeignKeyConstraint(
            ["accountId"],
            ["Account.id"],
            name=op.f("fk_TaxDependentAccounts_accountId_Account"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["deletedById"], ["User.id"], name=op.f("fk_TaxDependentAccounts_deletedById_User")
        ),
        sa.ForeignKeyConstraint(
            ["dependentId"],
            ["TaxBookDependent.id"],
            name=op.f("fk_TaxDependentAccounts_dependentId_TaxBookDependent"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("dependentId", "accountId", name=op.f("pk_TaxDependentAccounts")),
        info={"softDelete": True, "pairs": True},
    )


def downgrade() -> None:
    raise NotImplementedError("MoneyKata migrates forward only; restore a backup to go back")
