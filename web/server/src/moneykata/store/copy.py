"""Verified copies of the encrypted database: before a migration and for backups
(requirements S14.1.3, S14.6). SQLCipher's own export writes a copy under the same key."""

import os
from pathlib import Path

from sqlalchemy import Engine

from .db import connect


def export(engine: Engine, dest: Path, key: str | None) -> None:
    dest.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    tmp.unlink(missing_ok=True)
    with engine.connect() as conn:
        raw = conn.connection.dbapi_connection
        key_sql = f' KEY "{key}"' if key is not None else " KEY ''"
        raw.execute(f"ATTACH DATABASE '{tmp}' AS copy{key_sql}")
        try:
            raw.execute("SELECT sqlcipher_export('copy')")
        finally:
            raw.execute("DETACH DATABASE copy")
    os.chmod(tmp, 0o600)
    with open(tmp, "rb") as f:
        os.fsync(f.fileno())
    os.replace(tmp, dest)


def verify(path: Path, key: str | None) -> None:
    """Open the copy with its key and run PRAGMA integrity_check."""
    conn = connect(path, key)
    try:
        conn.execute("PRAGMA journal_mode = DELETE")
        result = conn.execute("PRAGMA integrity_check").fetchall()
    finally:
        conn.close()
    if result != [("ok",)]:
        raise RuntimeError(f"the copy {path.name} failed its integrity check")
