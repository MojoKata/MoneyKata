"""Remote users (requirements S10.3.3.1): a linked server's users kept as User records with
their link and their id there, never signing in here; usernames and emails unique among this
server's own users.

Revision: 0023
Follows: 0022
"""

import sqlalchemy as sa
from alembic import op

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("User", recreate="always") as batch_op:
        batch_op.add_column(sa.Column("linkId", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("remoteId", sa.Text(), nullable=True))
        batch_op.create_foreign_key("fk_User_linkId_Link", "Link", ["linkId"], ["id"])
        batch_op.create_check_constraint(
            op.f("ck_User_remote"),
            '"linkId" IS NULL OR ("passwordHash" IS NULL AND "twoStepAt" IS NULL '
            'AND "remoteId" IS NOT NULL)',
        )
        batch_op.drop_index("ux_User_username")
        batch_op.drop_index("ux_User_email")
        batch_op.create_index(
            "ux_User_username",
            ["username"],
            unique=True,
            sqlite_where=sa.text('NOT deleted AND "linkId" IS NULL'),
        )
        batch_op.create_index(
            "ux_User_email",
            ["email"],
            unique=True,
            sqlite_where=sa.text('NOT deleted AND "linkId" IS NULL'),
        )
        batch_op.create_index(
            "ux_User_linkId_remoteId",
            ["linkId", "remoteId"],
            unique=True,
            sqlite_where=sa.text("NOT deleted"),
        )


def downgrade() -> None:
    raise NotImplementedError("MoneyKata migrates forward only; restore a backup to go back")
