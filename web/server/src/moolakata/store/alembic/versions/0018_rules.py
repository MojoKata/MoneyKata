"""Categorisation and payee rules (requirements S2.7): a user's ordered rules, each matching a
payee as written (by text or `re:`) and, when given, an amount range, a direction and an
account, and setting a category, the payee shown and tags.

Revision: 0018
Follows: 0017
"""

import sqlalchemy as sa
from alembic import op

import moolakata.store.types

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "Rule",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("ownerId", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("payeeMatch", sa.Text(), nullable=False),
        sa.Column("amountMin", moolakata.store.types.Cents(), nullable=True),
        sa.Column("amountMax", moolakata.store.types.Cents(), nullable=True),
        sa.Column("direction", sa.Text(), server_default=sa.text("'any'"), nullable=False),
        sa.Column("accountId", sa.Text(), nullable=True),
        sa.Column("categoryId", sa.Text(), nullable=True),
        sa.Column("payee", sa.Text(), nullable=True),
        sa.Column("tags", sa.Text(), server_default=sa.text("'[]'"), nullable=False),
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
        sa.CheckConstraint("direction IN ('any', 'in', 'out')", name=op.f("ck_Rule_direction")),
        sa.CheckConstraint(
            "\"categoryId\" IS NOT NULL OR payee IS NOT NULL OR tags != '[]'",
            name=op.f("ck_Rule_sets_something"),
        ),
        sa.CheckConstraint(
            '"deletedAt" IS NOT NULL OR "deletedById" IS NULL', name=op.f("ck_Rule_deleted_by")
        ),
        sa.CheckConstraint("id GLOB 'Rule_*' AND length(id) = 31", name=op.f("ck_Rule_id")),
        sa.ForeignKeyConstraint(["ownerId"], ["User.id"], name=op.f("fk_Rule_ownerId_User")),
        sa.ForeignKeyConstraint(
            ["accountId"],
            ["Account.id"],
            name=op.f("fk_Rule_accountId_Account"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["categoryId"], ["Category.id"], name=op.f("fk_Rule_categoryId_Category")
        ),
        sa.ForeignKeyConstraint(
            ["deletedById"], ["User.id"], name=op.f("fk_Rule_deletedById_User")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_Rule")),
        info={"prefix": "Rule", "softDelete": True},
        sqlite_with_rowid=False,
    )
    with op.batch_alter_table("Rule", schema=None) as batch_op:
        batch_op.create_index("ix_Rule_owner", ["ownerId", "position"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("Rule", schema=None) as batch_op:
        batch_op.drop_index("ix_Rule_owner")
    op.drop_table("Rule")
