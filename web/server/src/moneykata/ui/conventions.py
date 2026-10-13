"""The API conventions of requirements S13.8, as pieces the routes share: money and quantities
as strings, cursor paging, versions with If-Match, and Idempotency-Key."""

import base64
import json
import threading
import time
from decimal import Decimal
from typing import Annotated, Any

from fastapi import Query, Request
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, PlainSerializer

from .. import money
from ..errors import Problem, refuse


def _money_in(v: Any) -> Decimal:
    if isinstance(v, Decimal):
        return v
    if not isinstance(v, str):
        raise ValueError('amounts are strings in dollars, such as "1234.50"')
    return money.parse(v, places=2)


def _quantity_in(v: Any) -> Decimal:
    if isinstance(v, Decimal):
        return v
    if not isinstance(v, str):
        raise ValueError('quantities and prices are decimal strings, such as "12.5"')
    return money.parse(v, places=money.QUANTITY_PLACES)


Money = Annotated[
    Decimal,
    BeforeValidator(_money_in),
    PlainSerializer(lambda d: money.money_str(d), return_type=str),
    Field(json_schema_extra={"type": "string", "format": "money", "examples": ["1234.50"]}),
]
Quantity = Annotated[
    Decimal,
    BeforeValidator(_quantity_in),
    PlainSerializer(lambda d: money.quantity_str(d), return_type=str),
    Field(json_schema_extra={"type": "string", "format": "decimal", "examples": ["12.5"]}),
]


class Model(BaseModel):
    """Every request and response body: camelCase as in the database, no extra fields."""

    model_config = ConfigDict(extra="forbid", populate_by_name=False)


class Page[T](BaseModel):
    items: list[T]
    next: str | None


DEFAULT_LIMIT = 100
MAX_LIMIT = 1000


class Paging:
    """?limit= and ?after=: a cursor names the last row seen by its sort key and id."""

    def __init__(
        self,
        limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
        after: str | None = Query(None, max_length=512),
    ):
        self.limit = limit
        self.after = decode_cursor(after) if after else None

    def page(self, rows: list, key) -> tuple[list, str | None]:
        """Rows fetched with limit + 1: the extra one says there is a next page."""
        more = len(rows) > self.limit
        rows = rows[: self.limit]
        nxt = encode_cursor(key(rows[-1])) if more and rows else None
        return rows, nxt


def encode_cursor(values: list | tuple) -> str:
    raw = json.dumps(list(values), default=str, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(text: str) -> list:
    try:
        raw = base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
        values = json.loads(raw)
    except (ValueError, json.JSONDecodeError):
        raise refuse("after", "bad-cursor", "This page link is not valid.", 400) from None
    if not isinstance(values, list):
        raise refuse("after", "bad-cursor", "This page link is not valid.", 400)
    return values


def if_match(request: Request) -> int:
    """The version a PATCH or DELETE was made against (S13.8.6)."""
    value = request.headers.get("if-match", "").strip().strip('"').removeprefix("W/").strip('"')
    if not value.isdigit():
        raise Problem(
            428 if not value else 400, "version-required", "Send the record's version in If-Match."
        )
    return int(value)


def stale(current: Any) -> Problem:
    """412 with the record as it is now, so the UI can show what changed."""
    body = current.model_dump(mode="json") if isinstance(current, BaseModel) else current
    return Problem(
        412, "stale-version", "Someone changed this since you loaded it.", extra={"current": body}
    )


class Idempotency:
    """A POST that creates may carry Idempotency-Key: a repeat within 24 hours gets the first
    answer (S13.8.8). Keys are per user."""

    TTL = 24 * 3600

    def __init__(self, clock=time.monotonic) -> None:
        self._seen: dict[tuple[str, str], tuple[float, int, Any, dict]] = {}
        self._lock = threading.Lock()
        self._clock = clock

    def lookup(self, user_id: str, key: str | None):
        if not key:
            return None
        with self._lock:
            self._prune()
            hit = self._seen.get((user_id, key))
        return hit[1:] if hit else None

    def remember(
        self, user_id: str, key: str | None, status: int, body: Any, headers: dict
    ) -> None:
        if not key:
            return
        with self._lock:
            self._seen[(user_id, key)] = (self._clock(), status, body, headers)

    def _prune(self) -> None:
        now = self._clock()
        for k in [k for k, v in self._seen.items() if now - v[0] > self.TTL]:
            del self._seen[k]
