"""Bringing the database to this release's revision (requirements §17.1.3): at start the
server copies the database (verified), then migrates it one revision per transaction, then
regenerates the Effective views. A database from a newer release refuses the start.

Until the first release there is one revision, 0001, regenerated as tables are added; from
the first release on, revisions are only ever added.

Migrations run with foreign keys off, as SQLite's table rebuilds need, and a foreign-key check
must come back clean before they are switched on again.

    python -m moneykata.store.migrate revise "message"   a new revision, generated from the
                                                         tables and reviewed by hand
"""

import datetime as dt
import logging
import sys
import tempfile
from pathlib import Path

from alembic import command
from alembic.config import Config as AlembicConfig
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine

from ..config import RefuseStart
from . import copy, views
from .db import make_engine
from .tables import metadata

log = logging.getLogger("moneykata.store")
HERE = Path(__file__).resolve().parent
VERSION_TABLE = "SchemaRevision"


def alembic_config(connection=None) -> AlembicConfig:
    cfg = AlembicConfig()
    cfg.set_main_option("path_separator", "os")
    cfg.set_main_option("script_location", str(HERE / "alembic"))
    cfg.set_main_option("version_locations", str(HERE / "alembic" / "versions"))
    cfg.set_main_option("revision_environment", "false")
    cfg.set_main_option("file_template", "%%(rev)s_%%(slug)s")
    if connection is not None:
        cfg.attributes["connection"] = connection
    return cfg


def head() -> str:
    return ScriptDirectory.from_config(alembic_config()).get_current_head()


def known() -> set[str]:
    return {s.revision for s in ScriptDirectory.from_config(alembic_config()).walk_revisions()}


def current(engine: Engine) -> str | None:
    with engine.connect() as conn:
        return MigrationContext.configure(
            conn, opts={"version_table": VERSION_TABLE}
        ).get_current_revision()


def upgrade(engine: Engine, db_path: Path, key: str | None, copies_dir: Path | None) -> bool:
    """Migrate to head. Returns whether anything changed."""
    rev = current(engine)
    if rev is not None and rev not in known():
        raise RefuseStart(
            f"the database is at revision {rev}, from a newer MoneyKata than "
            "this one; upgrade MoneyKata or restore an older backup"
        )
    target = head()
    if rev == target:
        with engine.begin() as conn:
            _sync_views(conn)
        return False
    if rev is not None and copies_dir is not None:
        stamp = dt.datetime.now(dt.UTC).strftime("%Y%m%d-%H%M%S")
        dest = copies_dir / f"moneykata-before-{target}-{stamp}.db"
        copy.export(engine, dest, key)
        copy.verify(dest, key)
        log.info("copied the database before migrating: %s", dest.name)
    with engine.connect() as conn:
        for sql in views.drop_all_sql(conn):
            conn.exec_driver_sql(sql)
        conn.commit()
        conn.exec_driver_sql("PRAGMA foreign_keys = OFF")
        try:
            command.upgrade(alembic_config(conn), "head")
            conn.commit()
            broken = conn.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
            if broken:
                raise RefuseStart(
                    f"the migration left {len(broken)} broken references; "
                    "restore the copy made before it"
                )
        finally:
            conn.exec_driver_sql("PRAGMA foreign_keys = ON")
    with engine.begin() as conn:
        _sync_views(conn)
    log.info("migrated the database from %s to %s", rev or "nothing", target)
    return True


def _sync_views(conn) -> None:
    views.sync(conn, metadata)


def revise(message: str) -> None:
    """Generate a revision from the difference between the tables and the revisions so far,
    on a throwaway plain SQLite database."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "revise.db"
        engine = make_engine(path, None)
        with engine.connect() as conn:
            command.upgrade(alembic_config(conn), "head")
            conn.commit()
            command.revision(
                alembic_config(conn),
                message=message,
                autogenerate=True,
                rev_id=f"{len(known()) + 1:04d}",
            )
            conn.commit()
        engine.dispose()


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "revise":
        revise(sys.argv[2])
    else:
        print(__doc__.strip())
        sys.exit(2)
