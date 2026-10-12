"""Column types (requirements §17.3, §17.9): money as integer cents, quantities and prices as
decimal text at a fixed scale, timestamps in UTC."""

import datetime as dt
from decimal import Decimal

from sqlalchemy import Integer, Text
from sqlalchemy.types import TypeDecorator

from .. import clock, money


class Cents(TypeDecorator):
    """Money: a Decimal in Python, integer cents in SQLite."""

    impl = Integer
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, float):
            raise TypeError("money is never a float")
        return money.to_cents(Decimal(value))

    def process_result_value(self, value, dialect):
        return money.from_cents(value)


class Dec(TypeDecorator):
    """A quantity or price: decimal text validated to 18 places."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, float):
            raise TypeError("quantities are never floats")
        d = Decimal(value)
        if d != money.quantity(d):
            raise ValueError(f"{value} has more than {money.QUANTITY_PLACES} places")
        return money.quantity_str(d)

    def process_result_value(self, value, dialect):
        return None if value is None else Decimal(value)


class UtcTimestamp(TypeDecorator):
    """A moment, stored in UTC as RFC 3339 text that sorts in time order."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if not isinstance(value, dt.datetime) or value.tzinfo is None:
            raise TypeError("timestamps must be timezone-aware")
        return value.astimezone(dt.UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return dt.datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=dt.UTC)


class Day(TypeDecorator):
    """A calendar date with no time zone: YYYY-MM-DD (§17.9.3)."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, dt.datetime) or not isinstance(value, dt.date):
            raise TypeError("dates are datetime.date")
        return value.isoformat()

    def process_result_value(self, value, dialect):
        return None if value is None else dt.date.fromisoformat(value)


def utcnow() -> dt.datetime:
    return clock.now()
