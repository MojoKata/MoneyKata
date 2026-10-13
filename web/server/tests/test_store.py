import datetime as dt
import os
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
            conn, opts={"version_table": "SchemaRevision", "compare_type": True}
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
        conn.exec_driver_sql(f"""UPDATE "Thing" SET deleted = 1, "deletedAt" = '{later}'""")
        conn.exec_driver_sql(f"""UPDATE "Part" SET deleted = 1, "deletedAt" = '{now}'""")
        row = conn.exec_driver_sql(
            'SELECT "effectiveDeleted", "effectiveDeletedAt" FROM "PartEffective"'
        ).one()
        assert row == (1, now)  # the earliest along the chain
        conn.exec_driver_sql("""UPDATE "Part" SET deleted = 0, "deletedAt" = NULL""")
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
    maintenance.open_store(keyed_config).db.dispose()
    copies = list((keyed_config.data_dir / "pre-upgrade").iterdir())
    assert len(copies) == 1 and calls == ["head"]
    assert os.stat(copies[0]).st_mode & 0o777 == 0o600


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


def test_revisions_migrate_a_database_from_0001_keeping_its_tokens(tmp_path):
    """Revisions rebuild tables to change a CHECK (0002 OneTimeToken, 0005 Share): what they
    hold is kept, and each rebuilt table is the one the declarations make."""
    from alembic import command

    engine = make_engine(tmp_path / "old.db", None)
    with engine.connect() as conn:
        command.upgrade(migrate.alembic_config(conn), "0001")
        conn.commit()
        uid = ids.new_id("User")
        conn.exec_driver_sql(
            'INSERT INTO "User" (id, username, "displayName", version, "createdAt", '
            f"\"updatedAt\", deleted) VALUES ('{uid}', 'alice', 'Alice', 1, "
            "'2026-10-01 00:00:00', '2026-10-01 00:00:00', 0)"
        )
        conn.exec_driver_sql(
            f"INSERT INTO \"OneTimeToken\" VALUES ('h1', 'invitation', '{uid}', NULL, "
            "'2026-10-01 00:00:00', '2030-01-01 00:00:00')"
        )
        conn.commit()
        command.upgrade(migrate.alembic_config(conn), "head")
        conn.commit()
        assert conn.exec_driver_sql('SELECT purpose FROM "OneTimeToken"').scalars().all() == [
            "invitation"
        ]
        conn.exec_driver_sql(
            f"INSERT INTO \"OneTimeToken\" VALUES ('h2', 'two-step', '{uid}', NULL, "
            "'2026-10-01 00:00:00', '2030-01-01 00:00:00')"
        )
        rebuilt = ("OneTimeToken", "Share")
        migrated = {
            name: conn.exec_driver_sql(
                f"SELECT sql FROM sqlite_master WHERE name = '{name}'"
            ).scalar_one()
            for name in rebuilt
        }
    engine.dispose()
    fresh = make_engine(tmp_path / "fresh.db", None)
    metadata.create_all(fresh, tables=[metadata.tables[n] for n in ("User", "Group", *rebuilt)])
    with fresh.connect() as conn:
        made = {
            name: conn.exec_driver_sql(
                f"SELECT sql FROM sqlite_master WHERE name = '{name}'"
            ).scalar_one()
            for name in rebuilt
        }
    fresh.dispose()
    squash = lambda sql: " ".join(sql.replace('"', "").split())  # noqa: E731
    for name in rebuilt:
        # The same columns and constraints, in whatever order the rebuild wrote them.
        assert sorted(squash(migrated[name])) == sorted(squash(made[name])), name
