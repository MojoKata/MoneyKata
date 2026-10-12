from dataclasses import dataclass

from . import Record


@dataclass(kw_only=True, eq=False)
class User(Record):
    id: str
    username: str
    displayName: str
    email: str | None = None
    active: bool = True
