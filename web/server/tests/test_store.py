import datetime as dt
import os
import re
import shutil
import sqlite3

import pytest
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Column, ForeignKey, MetaData, Table, Text, select, text

from moneykata import ids, settings
from moneykata.config import RefuseStart
from moneykata.keys import master
from moneykata.keys import secrets as sealing
from moneykata.store import maintenance, migrate, schema_check, views
from moneykata.store.db import Database, live, make_engine
from moneykata.store.entities.core import Secret
from moneykata.store.entities.users import User
from moneykata.store.repos import secrets as secret_repo
from moneykata.store.tables import metadata
from moneykata.store.tables._base import record
from moneykata.store.tables.receipts import is_search_table


def new_user(s, name="alice"):
    u = User(id=ids.new_id("User"), username=name, displayName=name.title())
    s.add(u)
    s.flush()
    return u


def test_database_is_encrypted_at_rest(store, keyed_config):
    with store.db.tx() as s:
        new_user(s)
    raw = keyed_config.db_path.read_bytes()
    assert b"SQLite format 3" not in raw[:100]
    assert b"alice" not in raw
    with pytest.raises(sqlite3.DatabaseError):
        sqlite3.connect(keyed_config.db_path).execute("SELECT * FROM User").fetchall()


def test_read_refuses_writes_and_tx_commits(db):
    with db.tx() as s:
        new_user(s)
    with db.read() as s:
        assert s.scalars(select(User)).one().username == "alice"
        with pytest.raises(Exception, match=r"readonly|query_only|attempt to write"):
            s.execute(text("UPDATE User SET displayName = 'x'"))


def test_versions_change_with_every_save(db):
    with db.tx() as s:
        u = new_user(s)
    assert u.version == 1
    with db.tx() as s:
        u = s.get(User, u.id)
        u.displayName = "Alice G."
    assert u.version == 2


def test_partial_unique_index_ignores_deleted(db):
    with db.tx() as s:
        a = new_user(s)
        a.mark_deleted(None)
    with db.tx() as s:
        new_user(s)  # the name can be used again
    with pytest.raises(Exception, match="UNIQUE"), db.tx() as s:
        new_user(s)


def test_tables_and_revisions_agree(db):
    with db.engine.connect() as conn:
        mc = MigrationContext.configure(
            conn,
            opts={
                "version_table": "SchemaRevision",
                "compare_type": True,
                "include_name": lambda name, type_, parent: (
                    type_ != "table" or not is_search_table(name)
                ),
            },
        )
        diff = compare_metadata(mc, metadata)
    assert diff == []
    assert migrate.current(db.engine) == migrate.head()


def test_schema_follows_the_conventions(db):
    assert schema_check.check_metadata(metadata) == []
    with db.engine.connect() as conn:
        assert schema_check.check_database(conn, metadata) == []


def test_schema_checks_catch_breaks():
    md = MetaData()
    Table(
        "Things",
        md,
        Column("id", Text, primary_key=True),
        Column("Bad_Name", Text),
        info={"softDelete": True},
    )
    problems = schema_check.check_metadata(md, "## 3. Prefixes\n\n| Prefix | Table |\n")
    assert any("singular" in p for p in problems)
    assert any("camelCase" in p for p in problems)
    assert any("WITHOUT ROWID" in p for p in problems)
    assert any("no row in schema.md" in p for p in problems)
    assert any("soft-delete" in p or "lacks" in p for p in problems)


def test_effective_views_follow_what_records_belong_to(tmp_path):
    from moneykata.store.tables import _base

    saved = _base.metadata
    md = MetaData(naming_convention=_base.NAMING)
    _base.metadata = md
    try:
        Table(
            "User",
            md,
            Column("id", Text, primary_key=True),
            info={"softDelete": False, "exception": "§4.4"},
        )
        parent = record("Thing", "Thng")
        child = record(
            "Part",
            "Part",
            Column("thingId", Text, ForeignKey("Thing.id", ondelete="CASCADE"), nullable=False),
        )
    finally:
        _base.metadata = saved
    engine = make_engine(tmp_path / "v.db", None)
    md.create_all(engine)
    with engine.begin() as conn:
        views.sync(conn, md)
        now = "2026-10-12T10:00:00.000000Z"
        later = "2026-10-12T11:00:00.000000Z"
        tid, pid = ids.new_id("Thng"), ids.new_id("Part")
        conn.execute(
            parent.insert().values(
                id=tid, createdAt=dt.datetime.now(dt.UTC), updatedAt=dt.datetime.now(dt.UTC)
            )
        )
        conn.execute(
            child.insert().values(
                id=pid,
                thingId=tid,
                createdAt=dt.datetime.now(dt.UTC),
                updatedAt=dt.datetime.now(dt.UTC),
            )
        )
        row = conn.exec_driver_sql('SELECT "effectiveDeleted" FROM "PartEffective"').one()
        assert row[0] == 0
        conn.exec_driver_sql(f"""UPDATE "Thing" SET "deletedAt" = '{later}'""")
        conn.exec_driver_sql(f"""UPDATE "Part" SET "deletedAt" = '{now}'""")
        row = conn.exec_driver_sql(
            'SELECT "effectiveDeleted", "effectiveDeletedAt" FROM "PartEffective"'
        ).one()
        assert row == (1, now)  # the earliest along the chain
        conn.exec_driver_sql("""UPDATE "Part" SET "deletedAt" = NULL""")
        row = conn.exec_driver_sql(
            'SELECT "effectiveDeleted", "effectiveDeletedAt" FROM "PartEffective"'
        ).one()
        assert row == (1, later)


def test_live_leaves_out_deleted_records(db):
    with db.tx() as s:
        a = new_user(s, "a")
        new_user(s, "b")
        a.mark_deleted(None)
    from moneykata.store.tables.users import User as UserTable

    with db.read() as s:
        names = [u.username for u in s.scalars(live(User, UserTable))]
    assert names == ["b"]


def test_a_newer_database_refuses_the_start(store, keyed_config):
    with store.db.engine.begin() as conn:
        conn.exec_driver_sql("UPDATE \"SchemaRevision\" SET version_num = '9999'")
    store.db.dispose()
    with pytest.raises(RefuseStart, match="newer MoneyKata"):
        maintenance.open_store(keyed_config)


def test_a_wrong_data_key_refuses_the_start(store, keyed_config):
    store.db.dispose()
    ring = master.read_keyring(keyed_config.keyring_path)
    key = keyed_config.key_file.read_bytes()
    fresh = master.wrap(key, master.new_data_key(), ring.master_created, master.now())
    master.write_keyring(keyed_config.keyring_path, fresh)
    with pytest.raises(RefuseStart, match="does not open with the data key"):
        maintenance.open_store(keyed_config)


def test_secrets_are_bound_to_their_record_and_field(store):
    key = store.keys.keys.secrets
    with store.db.tx() as s:
        secret_repo.put(s, key, "PriceSource", "Src_a", "apiKey", "tiingo-123", None)
        assert secret_repo.use(s, key, "PriceSource", "Src_a", "apiKey") == "tiingo-123"
        assert secret_repo.info(s, "PriceSource", "Src_a", "apiKey") is not None
        row = s.scalars(select(Secret)).one()
        assert b"tiingo-123" not in row.ciphertext
        sealed = sealing.Sealed(row.ciphertext, row.nonce, row.wrappedKey)
        with pytest.raises(sealing.SecretError):
            sealing.open_sealed(key, sealed, "PriceSource", "Src_b", "apiKey")
        with pytest.raises(sealing.SecretError):
            sealing.open_sealed(key, sealed, "PriceSource", "Src_a", "otherField")
        secret_repo.put(s, key, "PriceSource", "Src_a", "apiKey", "tiingo-456", None)
        assert len(s.scalars(select(Secret)).all()) == 1  # the old ciphertext is gone
        secret_repo.remove(s, "PriceSource", "Src_a", "apiKey")
        assert secret_repo.use(s, key, "PriceSource", "Src_a", "apiKey") is None


def test_settings_have_defaults_and_are_checked(db):
    from moneykata.errors import Problem

    with db.tx() as s:
        assert settings.get(s, "passwordMinLength") == 12
        settings.put(s, "passwordMinLength", 16, None)
        assert settings.get(s, "passwordMinLength") == 16
        with pytest.raises(Problem) as e:
            settings.put(s, "passwordMinLength", 6, None)
        assert e.value.errors[0].field == "passwordMinLength"
        with pytest.raises(Problem):
            settings.put(s, "backupTime", "25:00", None)
        assert settings.section(s, "backups") == {"backupTime": "02:30", "backupCopies": 14}


def test_backup_is_verified_restorable_and_pruned(store, keyed_config, tmp_path):
    with store.db.tx() as s:
        new_user(s)
    keyed_config.receipts_dir.mkdir(parents=True)
    (keyed_config.receipts_dir / "abc.mkr").write_bytes(b"sealed bytes")
    t0 = dt.datetime(2026, 10, 1, tzinfo=dt.UTC)
    made = [maintenance.backup(keyed_config, store, t0 + dt.timedelta(days=i)) for i in range(3)]
    key = keyed_config.key_file.read_bytes()
    for b in made:
        maintenance.check_backup(b, key)
        assert (b / "receipts" / "abc.mkr").exists()
    assert maintenance.prune(keyed_config, 2) == made[:1]
    assert maintenance.backups(keyed_config) == made[1:]

    # The restore of S15.6.8: the key from its phrase, the data directory from a backup.
    from moneykata.config import Config

    restored = Config(**{**keyed_config.__dict__, "data_dir": tmp_path / "restored"})
    restored.data_dir.mkdir()
    shutil.copy(made[-1] / "moneykata.db", restored.db_path)
    shutil.copy(made[-1] / "keyring", restored.keyring_path)
    again = maintenance.open_store(restored)
    with again.db.read() as s:
        assert s.scalars(select(User)).one().username == "alice"
    again.db.dispose()

    (made[-1] / "keyring").write_text((made[-1] / "keyring").read_text().replace("a", "b", 1))
    with pytest.raises(Exception):  # noqa: B017 - any failure: the copy changed
        maintenance.check_backup(made[-1], key)


def test_reencrypt_changes_the_data_key_and_keeps_everything(store, keyed_config):
    with store.db.tx() as s:
        new_user(s)
        secret_repo.put(s, store.keys.keys.secrets, "Smtp", "Smtp_x", "password", "hunter2", None)
    old_db_key = store.keys.keys.database
    store2 = maintenance.reencrypt(keyed_config, store)
    assert store2.keys.keys.database != old_db_key
    with store2.db.read() as s:
        assert (
            secret_repo.use(s, store2.keys.keys.secrets, "Smtp", "Smtp_x", "password") == "hunter2"
        )
    store2.db.dispose()
    store3 = maintenance.open_store(keyed_config)
    with store3.db.read() as s:
        assert s.scalars(select(User)).one().username == "alice"
    store3.db.dispose()


def test_an_interrupted_reencrypt_is_finished_at_start(store, keyed_config, monkeypatch):
    with store.db.tx() as s:
        secret_repo.put(s, store.keys.keys.secrets, "Smtp", "Smtp_x", "password", "hunter2", None)

    def crash(*a, **k):
        raise KeyboardInterrupt

    monkeypatch.setattr(maintenance, "_rewrap_secrets", crash)
    with pytest.raises(KeyboardInterrupt):
        maintenance.reencrypt(keyed_config, store)
    monkeypatch.undo()
    assert maintenance.next_keyring(keyed_config).exists()
    again = maintenance.open_store(keyed_config)
    assert not maintenance.next_keyring(keyed_config).exists()
    with again.db.read() as s:
        assert (
            secret_repo.use(s, again.keys.keys.secrets, "Smtp", "Smtp_x", "password") == "hunter2"
        )
    again.db.dispose()


def test_migration_copies_the_database_first(store, keyed_config, monkeypatch):
    with store.db.tx() as s:
        new_user(s)
    store.db.dispose()
    engine = make_engine(keyed_config.db_path, store.keys.keys.sqlcipher_key)
    with engine.begin() as conn:
        conn.exec_driver_sql("UPDATE \"SchemaRevision\" SET version_num = '0001'")
    engine.dispose()
    monkeypatch.setattr(migrate, "head", lambda: "0002")
    monkeypatch.setattr(migrate, "known", lambda: {"0001", "0002"})
    calls = []
    monkeypatch.setattr(migrate.command, "upgrade", lambda cfg, rev: calls.append(rev))
    older = keyed_config.data_dir / "pre-upgrade"
    older.mkdir()
    for i in range(3):  # three copies from earlier upgrades, oldest first
        (older / f"moneykata-before-000{i}-x.db").write_bytes(b"old")
        os.utime(older / f"moneykata-before-000{i}-x.db", (1_000_000 + i, 1_000_000 + i))
    maintenance.open_store(keyed_config).db.dispose()
    copies = sorted(p.name for p in older.iterdir())
    assert calls == ["head"]
    # The new copy and the two newest before it: the oldest is removed.
    assert len(copies) == migrate.PRE_UPGRADE_KEPT and "moneykata-before-0000-x.db" not in copies
    new = [p for p in older.iterdir() if "0002" in p.name and "-x" not in p.name]
    assert len(new) == 1 and os.stat(new[0]).st_mode & 0o777 == 0o600


def test_database_class_requires_a_unit_of_work(db):
    assert isinstance(db, Database)


def test_the_pool_keeps_connections_apart_across_threads(db):
    """Many requests at once each get their own connection, never a closed one."""
    import threading

    from sqlalchemy.pool import QueuePool

    assert isinstance(db.engine.pool, QueuePool)
    with db.tx() as s:
        new_user(s)
    failures = []

    def read():
        try:
            for _ in range(20):
                with db.read() as s:
                    s.scalars(select(User)).all()
        except Exception as e:
            failures.append(e)

    threads = [threading.Thread(target=read) for _ in range(16)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert failures == []


def test_a_backup_after_reads_still_writes_its_copy(store, keyed_config):
    """A pooled connection returns writable after a read (the backup's export needs it)."""
    for _ in range(5):
        with store.db.read() as s:
            s.scalars(select(User)).all()
    maintenance.backup(keyed_config, store)


def _clauses(sql: str) -> list[str]:
    """A CREATE statement's columns and constraints, in whatever order they were written, and
    a default with or without the parentheses Alembic writes around it."""
    sql = re.sub(r"DEFAULT \(('[^']*'|[\w.-]+)\)", r"DEFAULT \1", sql)
    return sorted(line.strip().rstrip(",").strip() for line in sql.splitlines() if line.strip())


def test_revisions_carry_a_database_from_0001_to_head(tmp_path):
    """Every revision after 0001, run as the server runs them: rows written at 0001 are kept,
    a deleted one stays deleted, rows referring to a rebuilt table keep their references with
    foreign keys back on, and each table ends as the declarations make it. The rows are written
    in 0001's terms, so they change only when 0001 does."""
    from alembic import command

    engine = make_engine(tmp_path / "old.db", None)
    stamp = "'2026-10-01 00:00:00'"
    uid, gone = ids.new_id("User"), ids.new_id("User")
    aid, iid, tid = ids.new_id("Acct"), ids.new_id("Imprt"), ids.new_id("Txn")
    with engine.connect() as conn:
        command.upgrade(migrate.alembic_config(conn), "0001")
        conn.commit()
        for statement in (
            'INSERT INTO "User" (id, username, "displayName", version, "createdAt", '
            f"\"updatedAt\", deleted) VALUES ('{uid}', 'alice', 'Alice', 1, {stamp}, {stamp}, 0)",
            'INSERT INTO "User" (id, username, "displayName", version, "createdAt", '
            f'"updatedAt", deleted, "deletedAt", "deletedById") VALUES (\'{gone}\', \'bob\', '
            f"'Bob', 1, {stamp}, {stamp}, 1, {stamp}, '{uid}')",
            'INSERT INTO "Account" (id, "ownerId", name, type, version, "createdAt", '
            f"\"updatedAt\", deleted) VALUES ('{aid}', '{uid}', 'Checking', 'checking', 1, "
            f"{stamp}, {stamp}, 0)",
            'INSERT INTO "Import" (id, "accountId", "userId", format, "fileName", "fileHash", '
            f"version, \"createdAt\", \"updatedAt\", deleted) VALUES ('{iid}', '{aid}', '{uid}', "
            f"'ofx', 'a.ofx', 'h', 1, {stamp}, {stamp}, 0)",
            'INSERT INTO "Transaction" (id, "accountId", date, kind, amount, "importId", '
            f"version, \"createdAt\", \"updatedAt\", deleted) VALUES ('{tid}', '{aid}', "
            f"'2026-10-01', 'deposit', '10.00', '{iid}', 1, {stamp}, {stamp}, 0)",
            'INSERT INTO "OneTimeToken" ("tokenHash", purpose, "userId", "createdAt", '
            f"\"expiresAt\") VALUES ('h1', 'invitation', '{uid}', {stamp}, '2030-01-01 00:00:00')",
        ):
            conn.exec_driver_sql(statement)
        conn.commit()
        before = {
            name: conn.exec_driver_sql(f'SELECT count(*) FROM "{name}"').scalar_one()
            for (name,) in conn.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type = 'table' "
                "AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'ReceiptSearch%'"
            )
        }

    assert migrate.upgrade(engine, tmp_path / "old.db", None, None)

    with engine.connect() as conn:
        assert conn.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
        assert conn.exec_driver_sql("PRAGMA foreign_key_check").fetchall() == []
        assert conn.exec_driver_sql("PRAGMA integrity_check").scalar() == "ok"
        for name, count in before.items():
            if name in metadata.tables:
                assert conn.exec_driver_sql(f'SELECT count(*) FROM "{name}"').scalar() == count
        users = conn.exec_driver_sql(
            'SELECT username, "effectiveDeleted" FROM "UserEffective" ORDER BY 1'
        ).all()
        assert [tuple(u) for u in users] == [("alice", 0), ("bob", 1)]
        txn = conn.exec_driver_sql(f'SELECT "importId" FROM "Transaction" WHERE id = \'{tid}\'')
        assert txn.scalar_one() == iid
        migrated = dict(
            conn.exec_driver_sql("SELECT name, sql FROM sqlite_master WHERE type = 'table'").all()
        )
    engine.dispose()

    fresh = make_engine(tmp_path / "fresh.db", None)
    metadata.create_all(fresh)
    with fresh.connect() as conn:
        made = dict(
            conn.exec_driver_sql("SELECT name, sql FROM sqlite_master WHERE type = 'table'").all()
        )
    fresh.dispose()
    differ = [n for n in metadata.tables if _clauses(migrated[n]) != _clauses(made[n])]
    assert differ == []


def test_restore_puts_a_backup_back_and_keeps_what_it_replaced(store, keyed_config):
    """`moneykata db restore` (S15.6.8): the backup checked, what it replaces moved aside, and
    the restored database opens at the server's next start."""
    with store.db.tx() as s:
        new_user(s, "alice")
    keyed_config.receipts_dir.mkdir(parents=True)
    (keyed_config.receipts_dir / "abc.mkr").write_bytes(b"sealed bytes")
    made = maintenance.backup(keyed_config, store)
    assert maintenance.verify_backup(keyed_config) == made
    with store.db.tx() as s:
        new_user(s, "bob")
    (keyed_config.receipts_dir / "later.mkr").write_bytes(b"after the backup")
    store.db.dispose()

    held = maintenance.lock_data_dir(keyed_config, "test")
    with pytest.raises(RefuseStart, match="stop the server before restoring"):
        maintenance.restore(keyed_config, made)
    held.close()

    aside = maintenance.restore(keyed_config, made)
    assert sorted(p.name for p in (aside / "receipts").iterdir()) == ["abc.mkr", "later.mkr"]
    assert sorted(p.name for p in keyed_config.receipts_dir.iterdir()) == ["abc.mkr"]
    again = maintenance.open_store(keyed_config)
    with again.db.read() as s:
        assert [u.username for u in s.scalars(select(User))] == ["alice"]
    again.db.dispose()


def test_restore_refuses_a_changed_backup_or_one_from_a_newer_release(store, keyed_config):
    made = maintenance.backup(keyed_config, store)
    store.db.dispose()
    manifest = made / "manifest.json"
    manifest.write_text(manifest.read_text().replace('"revision": "0002"', '"revision": "9999"'))
    with pytest.raises(RefuseStart, match="from a newer MoneyKata"):
        maintenance.restore(keyed_config, made)
    assert keyed_config.db_path.exists()  # nothing was moved
    with open(made / "moneykata.db", "ab") as f:
        f.write(b"x")
    with pytest.raises(RuntimeError, match="has changed since the backup"):
        maintenance.verify_backup(keyed_config, made)
