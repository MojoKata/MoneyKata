"""The MoolaKata Connector (requirements S18): the paired connector and each user's
Connections, and an account's sync (its Connection and institution account, S18.6.2).

`Account` is rebuilt to add its columns and the foreign key, as 0004 rebuilds tables.

Revision: 0011
Follows: 0010
"""

import sqlalchemy as sa
from alembic import op

from moolakata.store.types import UtcTimestamp

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

ACCOUNT_COLUMNS = (
    '"statementIntervalDismissed" TEXT, \n',
    '"statementIntervalDismissed" TEXT, \n\t"connectionId" TEXT, \n\t"syncAccount" TEXT, \n',
)
ACCOUNT_KEY = (
    'CONSTRAINT "fk_Account_deletedById_User" FOREIGN KEY("deletedById") REFERENCES "User" (id), \n',
    'CONSTRAINT "fk_Account_deletedById_User" FOREIGN KEY("deletedById") REFERENCES "User" (id), \n'
    '\tCONSTRAINT "fk_Account_connectionId_Connection" FOREIGN KEY("connectionId") '
    'REFERENCES "Connection" (id), \n',
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
    op.create_table(
        "Connector",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("codeHash", sa.Text(), nullable=True),
        sa.Column("codeExpiresAt", UtcTimestamp(), nullable=True),
        sa.Column("identityKey", sa.Text(), nullable=True),
        sa.Column("sealingKey", sa.Text(), nullable=True),
        sa.Column("pairedAt", UtcTimestamp(), nullable=True),
        sa.Column("pairedById", sa.Text(), nullable=True),
        sa.Column("endedAt", UtcTimestamp(), nullable=True),
        sa.Column("endedById", sa.Text(), nullable=True),
        sa.Column("lastReportAt", UtcTimestamp(), nullable=True),
        sa.Column("locked", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("connectorVersion", sa.Text(), nullable=True),
        sa.Column("protocol", sa.Integer(), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("createdAt", UtcTimestamp(), nullable=False),
        sa.Column("updatedAt", UtcTimestamp(), nullable=False),
        sa.Column(
            "deleted",
            sa.Boolean(),
            sa.Computed('"deletedAt" IS NOT NULL', persisted=False),
            nullable=True,
        ),
        sa.Column("deletedAt", UtcTimestamp(), nullable=True),
        sa.Column("deletedById", sa.Text(), nullable=True),
        sa.CheckConstraint("id GLOB 'Cnctr_*' AND length(id) = 32", name=op.f("ck_Connector_id")),
        sa.CheckConstraint(
            "state IN ('pairing', 'paired', 'ended')", name=op.f("ck_Connector_state")
        ),
        sa.CheckConstraint(
            '"deletedAt" IS NOT NULL OR "deletedById" IS NULL', name=op.f("ck_Connector_deleted_by")
        ),
        sa.ForeignKeyConstraint(
            ["deletedById"], ["User.id"], name=op.f("fk_Connector_deletedById_User")
        ),
        sa.ForeignKeyConstraint(
            ["endedById"], ["User.id"], name=op.f("fk_Connector_endedById_User")
        ),
        sa.ForeignKeyConstraint(
            ["pairedById"], ["User.id"], name=op.f("fk_Connector_pairedById_User")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_Connector")),
        sqlite_with_rowid=False,
    )
    with op.batch_alter_table("Connector", schema=None) as batch_op:
        batch_op.create_index(
            "ux_Connector_identityKey",
            ["identityKey"],
            unique=True,
            sqlite_where=sa.text("NOT deleted"),
        )

    op.create_table(
        "Connection",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("ownerId", sa.Text(), nullable=False),
        sa.Column("connectorId", sa.Text(), nullable=False),
        sa.Column("driver", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("lastRunAt", UtcTimestamp(), nullable=True),
        sa.Column("lastRunAdded", sa.Integer(), nullable=True),
        sa.Column("institutionAccounts", sa.Text(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column("settings", sa.Text(), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("sealedCredential", sa.Text(), nullable=True),
        sa.Column("sealedAt", UtcTimestamp(), nullable=True),
        sa.Column("signInAddress", sa.Text(), nullable=True),
        sa.Column("removedAt", UtcTimestamp(), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("createdAt", UtcTimestamp(), nullable=False),
        sa.Column("updatedAt", UtcTimestamp(), nullable=False),
        sa.Column(
            "deleted",
            sa.Boolean(),
            sa.Computed('"deletedAt" IS NOT NULL', persisted=False),
            nullable=True,
        ),
        sa.Column("deletedAt", UtcTimestamp(), nullable=True),
        sa.Column("deletedById", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "driver IN ('folder', 'ofx-direct', 'schwab')", name=op.f("ck_Connection_driver")
        ),
        sa.CheckConstraint("id GLOB 'Conn_*' AND length(id) = 31", name=op.f("ck_Connection_id")),
        sa.CheckConstraint(
            "state IN ('new', 'ok', 'needs-sign-in', 'failing', 'removed')",
            name=op.f("ck_Connection_state"),
        ),
        sa.CheckConstraint(
            '"deletedAt" IS NOT NULL OR "deletedById" IS NULL',
            name=op.f("ck_Connection_deleted_by"),
        ),
        sa.ForeignKeyConstraint(
            ["connectorId"], ["Connector.id"], name=op.f("fk_Connection_connectorId_Connector")
        ),
        sa.ForeignKeyConstraint(
            ["deletedById"], ["User.id"], name=op.f("fk_Connection_deletedById_User")
        ),
        sa.ForeignKeyConstraint(
            ["ownerId"],
            ["User.id"],
            name=op.f("fk_Connection_ownerId_User"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_Connection")),
        sqlite_with_rowid=False,
    )
    with op.batch_alter_table("Connection", schema=None) as batch_op:
        batch_op.create_index(
            "ux_Connection_ownerId_label",
            ["ownerId", "label"],
            unique=True,
            sqlite_where=sa.text("NOT deleted"),
        )

    rebuild(op.get_bind(), "Account", [ACCOUNT_COLUMNS, ACCOUNT_KEY])


def downgrade() -> None:
    raise NotImplementedError("MoolaKata migrates forward only; restore a backup to go back")
