"""The linked copy's own database (requirements S11.9.1, S11.9.11): what a link brought in,
under the copy's key. It keeps its own history of revisions, applied when the copy is opened."""

from sqlalchemy import (
    Column,
    Engine,
    Integer,
    MetaData,
    Table,
    Text,
)

metadata = MetaData()

# Each shared item as it arrived: its kind, owner, the people here it names, and its version.
Item = Table(
    "Item",
    metadata,
    Column("id", Text, primary_key=True),  # the item's id at its source
    Column("kind", Text, nullable=False),
    Column("name", Text, nullable=False),
    Column("ownerName", Text, nullable=False),
    Column("viewers", Text, nullable=False),  # JSON: local user ids it names
    Column("version", Integer, nullable=False),
    Column("asOf", Text, nullable=False),
)

# What its screens show, worked out at its source (S11.3.1): one document a screen request, as
# the person it was worked out for sees it.
Doc = Table(
    "Doc",
    metadata,
    Column("itemId", Text, primary_key=True),
    Column("path", Text, primary_key=True),  # the screen's API path, with its query
    Column("viewer", Text, primary_key=True),  # the local user it was worked out for
    Column("body", Text, nullable=False),  # JSON, as the source's API answered it
)

# A receipt or a tax book's document file that crossed (S11.9.6): its sealed file's name and
# the length and hash of its plain bytes, as signed at the source.
File = Table(
    "File",
    metadata,
    Column("id", Text, primary_key=True),  # its id at the source
    Column("itemId", Text, nullable=False),
    Column("fileName", Text, nullable=False),  # random, under receipts/
    Column("contentType", Text, nullable=False),
    Column("length", Integer, nullable=False),
    Column("sha256", Text, nullable=False),
    Column("thumbnail", Text),  # data URL
    Column("meta", Text, nullable=False),  # JSON: date, amount, payee, text read
)

# The changes applied, in order (S11.9.5).
Applied = Table(
    "Applied",
    metadata,
    Column("seq", Integer, primary_key=True),
    Column("appliedAt", Text, nullable=False),
)

Revision = Table("Revision", metadata, Column("n", Integer, primary_key=True))

# Each revision of the copy's schema, in order; the copy records the last one applied.
REVISIONS = [lambda conn: metadata.create_all(conn)]


def upgrade(engine: Engine) -> int:
    with engine.begin() as conn:
        Revision.create(conn, checkfirst=True)
        have = conn.exec_driver_sql('SELECT max(n) FROM "Revision"').scalar() or 0
        for n, step in enumerate(REVISIONS[have:], start=have + 1):
            step(conn)
            conn.execute(Revision.insert().values(n=n))
        return len(REVISIONS)
