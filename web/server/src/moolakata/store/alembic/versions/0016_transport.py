"""Transport (requirements S11.1.3, S11.6, S11.9): the peer's copy key, which this side seals
its changes and receipts to; the peer's own TLS certificate, pinned by its key's fingerprint,
with the next one it announced and one it presented unannounced; and when the peer answered
that it has no link with this one.

`Link` is rebuilt, as 0014 rebuilds its tables.

Revision: 0016
Follows: 0015
"""

from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None

LINK = (
    '"gotSeq" INTEGER DEFAULT 0 NOT NULL, \n',
    '"gotSeq" INTEGER DEFAULT 0 NOT NULL, \n\t"peerCopyKey" TEXT, \n\t"peerCert" TEXT, \n'
    '\t"peerCertNext" TEXT, \n\t"peerCertOffered" TEXT, \n\t"brokenAt" TEXT, \n',
)
COLUMNS = ("peerCopyKey", "peerCert", "peerCertNext", "peerCertOffered", "brokenAt")


def rebuild(conn, name: str, edits: list[tuple[str, str]], drop: tuple[str, ...] = ()) -> None:
    sql = conn.exec_driver_sql(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)
    ).scalar_one()
    stored = [
        r[1]
        for r in conn.exec_driver_sql(f'PRAGMA table_xinfo("{name}")').fetchall()
        if r[6] == 0 and r[1] not in drop
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
    rebuild(op.get_bind(), "Link", [LINK])


def downgrade() -> None:
    rebuild(op.get_bind(), "Link", [(LINK[1], LINK[0])], drop=COLUMNS)
