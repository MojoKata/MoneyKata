"""The API conventions of requirements S13.8, as pieces the routes share: money, quantities
and ratios as exact JSON numbers, cursor paging, versions with If-Match, and Idempotency-Key."""

import base64
import json
import threading
import time
from decimal import Decimal
from typing import Annotated, Any

from fastapi import Query, Request, Response
from fastapi.routing import APIRoute
from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    PlainSerializer,
    WithJsonSchema,
)

from .. import exactjson, money
from ..errors import Problem, refuse


class Sent(Decimal):
    """A number as a request sent it, so its places are checked; a Decimal the server worked
    out (an average, say) is rounded when it is written instead."""


def _money_in(v: Any) -> Decimal:
    if isinstance(v, float):
        raise ValueError("amounts are exact: send the number as written, never through a float")
    if type(v) is Decimal:
        return v
    return money.parse(v, places=2)


def _quantity_in(v: Any) -> Decimal:
    if isinstance(v, float):
        raise ValueError("quantities are exact: send the number as written, never through a float")
    if type(v) is Decimal:
        return v
    return money.parse(v, places=money.QUANTITY_PLACES)


def _money_out(d: Decimal) -> str:
    return exactjson.mark(money.money_str(d) or "0")


def _quantity_out(d: Decimal) -> str:
    return exactjson.mark(exactjson.text(Decimal(money.quantity_str(d) or "0")))


# Exact numbers in JSON (S13.8.2): read from a number (or a decimal string, as a form field
# gives it), written as a number literal with its own digits, never a float. In Python they
# are Decimals; `when_used="json"` leaves `model_dump()` giving Decimals.
Money = Annotated[
    Decimal,
    BeforeValidator(_money_in),
    PlainSerializer(_money_out, return_type=str, when_used="json"),
    WithJsonSchema({"type": "number", "format": "money", "examples": [1234.5]}),
]
Quantity = Annotated[
    Decimal,
    BeforeValidator(_quantity_in),
    PlainSerializer(_quantity_out, return_type=str, when_used="json"),
    WithJsonSchema({"type": "number", "format": "decimal", "examples": [12.5]}),
]


def _ratio_in(v: Any) -> Decimal:
    if isinstance(v, float):  # worked out by the server, so by its shortest digits
        return Decimal(repr(v))
    return money.parse(v)


def _ratio_out(d: Decimal) -> str:
    return exactjson.mark(exactjson.text(d.normalize() if d == d.to_integral_value() else d))


# A share or rate the server works out for display (a percentage, a factor, years): an exact
# number like the rest, never a binary float.
Ratio = Annotated[
    Decimal,
    BeforeValidator(_ratio_in),
    PlainSerializer(_ratio_out, return_type=str, when_used="json"),
    WithJsonSchema({"type": "number", "format": "decimal", "examples": [12.5]}),
]
# Free-form data a request carries (a projection's inputs, the assumptions, settings), for code
# that works in floats: its numbers arrive as floats, as plain JSON would give them.
Loose = Annotated[dict, BeforeValidator(exactjson.plain)]


class ExactRequest(Request):
    """A request whose JSON body keeps its numbers exact: `1234.50` arrives as a Decimal."""

    async def json(self) -> Any:
        if not hasattr(self, "_json"):
            body = await self.body()
            self._json = json.loads(body, parse_float=Sent) if body else None
        return self._json


class ExactRoute(APIRoute):
    """Every API route (S13.8.2): exact numbers in the request body, and the marks on exact
    numbers taken off the response, whichever way FastAPI wrote it."""

    def get_route_handler(self):
        handler = super().get_route_handler()

        async def exact(request: Request) -> Response:
            response = await handler(ExactRequest(request.scope, request.receive))
            kind = response.headers.get("content-type", "")
            if "json" in kind and hasattr(response, "body") and response.body:
                body = exactjson.unmark_bytes(bytes(response.body))
                if len(body) != len(response.body):
                    response.body = body
                    response.headers["content-length"] = str(len(body))
            return response

        return exact


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
    raw = exactjson.dumps(list(values), default=str, separators=(",", ":")).encode()
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
