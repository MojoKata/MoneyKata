"""Record ids (schema.md §2): a prefix, an underscore, and a UUIDv7 in 26 lowercase Crockford
base-32 digits, most significant first, so ids sort by creation time."""

import os
import re
import threading
import time
import uuid

ALPHABET = "0123456789abcdefghjkmnpqrstvwxyz"
_DECODE = {c: i for i, c in enumerate(ALPHABET)}
PREFIX = re.compile(r"^[A-Z][A-Za-z]{0,4}$")
_lock = threading.Lock()
_last = (0, 0)


def uuid7() -> uuid.UUID:
    """A UUIDv7 whose 12-bit counter keeps ids made in the same millisecond in order."""
    global _last
    with _lock:
        ms = time.time_ns() // 1_000_000
        last_ms, counter = _last
        if ms <= last_ms:
            ms, counter = last_ms, counter + 1
            if counter > 0xFFF:
                ms, counter = last_ms + 1, 0
        else:
            counter = int.from_bytes(os.urandom(2)) & 0x3FF
        _last = (ms, counter)
    rand = int.from_bytes(os.urandom(8)) & ((1 << 62) - 1)
    value = (ms << 80) | (0x7 << 76) | (counter << 64) | (0b10 << 62) | rand
    return uuid.UUID(int=value)


def encode(u: uuid.UUID) -> str:
    n = u.int
    out = []
    for _ in range(26):
        out.append(ALPHABET[n & 31])
        n >>= 5
    return "".join(reversed(out))


def decode(text: str) -> uuid.UUID:
    if len(text) != 26 or text[0] not in "01234567":
        raise ValueError("not a 26-digit id")
    n = 0
    for c in text:
        if c not in _DECODE:
            raise ValueError(f"{c!r} is not in the id alphabet")
        n = (n << 5) | _DECODE[c]
    return uuid.UUID(int=n)


def new_id(prefix: str) -> str:
    if not PREFIX.match(prefix):
        raise ValueError(f"bad prefix {prefix!r}")
    return f"{prefix}_{encode(uuid7())}"


def prefix_of(record_id: str) -> str:
    return record_id.split("_", 1)[0]


def is_id(value: str, prefix: str) -> bool:
    head, sep, tail = value.partition("_")
    if head != prefix or not sep:
        return False
    try:
        decode(tail)
    except ValueError:
        return False
    return True
