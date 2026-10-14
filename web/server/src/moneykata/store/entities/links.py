import datetime as dt
from dataclasses import dataclass

from . import Record


@dataclass(kw_only=True, eq=False)
class Link(Record):
    id: str
    state: str
    role: str
    peerName: str | None = None
    householdName: str | None = None
    householdAvatar: str | None = None
    address: str | None = None
    peerKey: str | None = None
    codeHash: str | None = None
    codeExpiresAt: dt.datetime | None = None
    createdById: str | None = None
    approvedById: str | None = None
    approvedAt: dt.datetime | None = None
    lastOkAt: dt.datetime | None = None
    lastError: str | None = None
    failingSince: dt.datetime | None = None
    peerVersion: str | None = None
    peerProtocol: int | None = None
    endedAt: dt.datetime | None = None
