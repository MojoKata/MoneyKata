"""Stored secrets (requirements S14.4): sealed on their own, decrypted only when used, and
never sent to the browser. A replaced or removed secret's old ciphertext is deleted outright
(schema.md §4.4.2)."""

import datetime as dt
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ... import ids
from ...keys import secrets as sealing
from ..entities.core import Secret


@dataclass(frozen=True)
class SecretInfo:
    """What the UI shows of a secret: that it is set, when and by whom."""

    setAt: dt.datetime
    setById: str | None


def put(
    s: Session, key: bytes, record_type: str, record_id: str, field: str, value: str, by: str | None
) -> None:
    remove(s, record_type, record_id, field)
    sealed = sealing.seal(key, value, record_type, record_id, field)
    s.add(
        Secret(
            id=ids.new_id("Secr"),
            recordType=record_type,
            recordId=record_id,
            field=field,
            ciphertext=sealed.ciphertext,
            nonce=sealed.nonce,
            wrappedKey=sealed.wrappedKey,
            setById=by,
        )
    )
    s.flush()


def remove(s: Session, record_type: str, record_id: str, field: str) -> None:
    s.execute(
        delete(Secret).where(
            Secret.recordType == record_type, Secret.recordId == record_id, Secret.field == field
        )
    )


def _row(s: Session, record_type: str, record_id: str, field: str) -> Secret | None:
    return s.scalars(
        select(Secret).where(
            Secret.recordType == record_type, Secret.recordId == record_id, Secret.field == field
        )
    ).first()


def info(s: Session, record_type: str, record_id: str, field: str) -> SecretInfo | None:
    row = _row(s, record_type, record_id, field)
    return SecretInfo(row.setAt, row.setById) if row else None


def use(s: Session, key: bytes, record_type: str, record_id: str, field: str) -> str | None:
    """The plain value, for one call. Callers never keep or log it."""
    row = _row(s, record_type, record_id, field)
    if row is None:
        return None
    return sealing.open_sealed(
        key,
        sealing.Sealed(row.ciphertext, row.nonce, row.wrappedKey),
        record_type,
        record_id,
        field,
    )
