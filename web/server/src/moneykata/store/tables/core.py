"""Settings, secrets and the background tasks' last runs."""

from sqlalchemy import Column, ForeignKey, LargeBinary, Text, UniqueConstraint

from ..types import UtcTimestamp
from ._base import exception, keyed

Setting = keyed(
    "Setting",
    Column("key", Text, primary_key=True),
    Column("value", Text, nullable=False),
    Column("updatedById", Text, ForeignKey("User.id")),
)

Secret = exception(
    "Secret",
    "a secret's old ciphertext is removed when it is replaced or removed (§4.4.2)",
    Column("recordType", Text, nullable=False),
    Column("recordId", Text, nullable=False),
    Column("field", Text, nullable=False),
    Column("ciphertext", LargeBinary, nullable=False),
    Column("nonce", LargeBinary, nullable=False),
    Column("wrappedKey", LargeBinary, nullable=False),
    Column("setAt", UtcTimestamp, nullable=False),
    Column("setById", Text, ForeignKey("User.id")),
    UniqueConstraint("recordType", "recordId", "field"),
    prefix="Secr",
)

TaskRun = exception(
    "TaskRun",
    "work state: a background task's last run (§4.4.4)",
    Column("name", Text, primary_key=True),
    Column("startedAt", UtcTimestamp, nullable=False),
    Column("finishedAt", UtcTimestamp),
    Column("error", Text),
)
