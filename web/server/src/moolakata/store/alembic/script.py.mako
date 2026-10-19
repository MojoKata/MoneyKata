"""${message}

Revision: ${up_revision}
% if down_revision:
Follows: ${down_revision | comma,n}
% endif
"""

import sqlalchemy as sa
from alembic import op

import moolakata.store.types
${imports if imports else ""}
revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    raise NotImplementedError("MoolaKata migrates forward only; restore a backup to go back")
