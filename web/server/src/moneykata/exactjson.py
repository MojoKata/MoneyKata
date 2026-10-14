"""JSON with exact numbers (requirements S13.8.2): a `Decimal` is written as a number literal
with its own digits (`1234.50`), never as a float or a string, and a number with a decimal
point is read back as a `Decimal`.

Neither Pydantic nor the standard library writes a `Decimal` as a number, so a decimal is first
written as a marked string, `"\\u0000<token>#1234.50"`, and the mark is then taken off the
finished JSON text, leaving `1234.50`. The token is random for each process, so no text a
person types can carry a mark. Every JSON this server sends goes through `dumps` or `unmark`:
the API's responses (`ExactRoute`), the live stream, MCP and the link protocol.
"""

import json
import re
import secrets
from decimal import Decimal
from typing import Any

_TOKEN = secrets.token_hex(8)
_MARK = f"\x00{_TOKEN}#"
# The mark as JSON writes it: the NUL escaped, inside the string's quotes.
_MARKED = re.compile(r'"\\u0000' + _TOKEN + r'#(-?[0-9]+(?:\.[0-9]+)?)"')
_MARKED_BYTES = re.compile(_MARKED.pattern.encode())


def text(d: Decimal) -> str:
    """A decimal's digits, always with a decimal point, so a reader can tell it from an
    integer: `5` is written `5.0`."""
    s = format(d, "f")
    if s in ("-0", "-0.0"):
        s = "0"
    return s if "." in s else s + ".0"


def mark(d: Decimal | str) -> str:
    """A decimal as the marked string that becomes a number literal in the finished JSON."""
    return _MARK + (d if isinstance(d, str) else text(d))


def marked(obj: Any) -> Any:
    """Free-form data (a dict typed `Any` in a response) with every Decimal marked, so it is
    written as an exact number like a declared field, not as a string."""
    if isinstance(obj, Decimal):
        return mark(obj)
    if isinstance(obj, dict):
        return {k: marked(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return [marked(v) for v in obj]
    return obj


def plain(obj: Any) -> Any:
    """Free-form data from a request, for code that works in floats (a projection's inputs,
    the assumptions, settings): every Decimal as a float."""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: plain(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return [plain(v) for v in obj]
    return obj


def unmark(s: str) -> str:
    return _MARKED.sub(r"\1", s)


def unmark_bytes(b: bytes) -> bytes:
    return _MARKED_BYTES.sub(rb"\1", b) if b"\\u0000" in b else b


def _default(o: Any) -> Any:
    if isinstance(o, Decimal):
        return mark(o)
    raise TypeError(f"{type(o).__name__} is not JSON")


def dumps(obj: Any, **kw: Any) -> str:
    """`json.dumps`, with every `Decimal` (and every marked string) as an exact number. A
    `default` given handles whatever else isn't JSON."""
    other = kw.pop("default", None)

    def default(o: Any) -> Any:
        if isinstance(o, Decimal) or other is None:
            return _default(o)
        return other(o)

    return unmark(json.dumps(obj, default=default, **kw))


def loads(s: str | bytes) -> Any:
    """`json.loads`, with every number that has a decimal point or an exponent as a `Decimal`."""
    return json.loads(s, parse_float=Decimal)
