"""Emails queued in the database (requirements S16.2, S15.1.7): an email waiting to go out
through SMTP is kept in the encrypted database, not in `outbox/` in the clear, until it is sent
or its link expires. What an earlier release left in `outbox/` is moved in by the mail task.

Revision: 0025
Follows: 0024
"""

import sqlalchemy as sa
from alembic import op

import moolakata.store.types

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "QueuedEmail",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("recipient", sa.Text(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("queuedAt", moolakata.store.types.UtcTimestamp(), nullable=False),
        sa.Column("expiresAt", moolakata.store.types.UtcTimestamp(), nullable=False),
        sa.Column("refusedAt", moolakata.store.types.UtcTimestamp(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.CheckConstraint("id GLOB 'Email_*' AND length(id) = 32", name=op.f("ck_QueuedEmail_id")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_QueuedEmail")),
        info={
            "softDelete": False,
            "exception": "a work queue: removed when sent or when its link expires (§4.4.4)",
            "prefix": "Email",
        },
        sqlite_with_rowid=False,
    )
    with op.batch_alter_table("QueuedEmail", schema=None) as batch_op:
        batch_op.create_index("ix_QueuedEmail_queuedAt", ["queuedAt"], unique=False)


def downgrade() -> None:
    raise NotImplementedError("MoolaKata migrates forward only; restore a backup to go back")
