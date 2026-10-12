"""Alembic's environment: always handed a connection by store/migrate.py, never a URL, since
the database opens only with its key."""

from alembic import context

from moneykata.store.tables import metadata

VERSION_TABLE = "SchemaRevision"

connection = context.config.attributes["connection"]
context.configure(
    connection=connection,
    target_metadata=metadata,
    version_table=VERSION_TABLE,
    render_as_batch=True,
    transaction_per_migration=True,
    compare_type=True,
    include_object=lambda obj, name, type_, reflected, compare_to: (
        not (type_ == "table" and name == VERSION_TABLE)
    ),
)
with context.begin_transaction():
    context.run_migrations()
