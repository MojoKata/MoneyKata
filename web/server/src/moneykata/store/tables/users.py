"""Users (requirements §13.1)."""

from sqlalchemy import Boolean, Column, Text, text

from ._base import record, unique_live

User = record(
    "User",
    "User",
    Column("username", Text, nullable=False),
    Column("displayName", Text, nullable=False),
    Column("email", Text),
    Column("active", Boolean, nullable=False, server_default=text("1")),
)
unique_live(User, "username")
