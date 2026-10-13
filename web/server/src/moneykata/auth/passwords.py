"""Passwords (requirements S13.7.3): argon2id at 64 MiB, 3 passes, parallelism 1; the minimum
length Settings set, and no other rule than refusing the 100,000 most common passwords (the
UK NCSC's list, shipped with the app)."""

import gzip
from functools import cache
from pathlib import Path

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

COMMON_FILE = Path(__file__).with_name("common-passwords.txt.gz")
PARAMS = {"time_cost": 3, "memory_cost": 64 * 1024, "parallelism": 1, "type": Type.ID}
_hasher = PasswordHasher(**PARAMS)


def use_fast_hashing_for_tests() -> None:
    """Tests sign in hundreds of times; they trade the cost for speed. Never at run time."""
    global _hasher
    _hasher = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1, type=Type.ID)


@cache
def common() -> frozenset[str]:
    return frozenset(gzip.decompress(COMMON_FILE.read_bytes()).decode().split("\n")) - {""}


def problem(password: str, min_length: int) -> tuple[str, str] | None:
    """Why a new password is refused, as (code, message), or None."""
    if len(password) < min_length:
        return "password-too-short", f"Use at least {min_length} characters."
    if len(password) > 1024:
        return "password-too-long", "Use at most 1,024 characters."
    if password in common() or password.lower() in common():
        return "password-too-common", (
            "This password is on the list of the most common ones. Choose another."
        )
    return None


def hash_password(password: str) -> str:
    return _hasher.hash(password)


_DUMMY: list[str] = []


def verify(stored: str | None, password: str) -> bool:
    """Check a password; with no stored hash, spend the same time and fail, so a missing
    user can't be told from a wrong password by timing."""
    if not _DUMMY:
        _DUMMY.append(_hasher.hash("moneykata timing dummy"))
    try:
        return _hasher.verify(stored or _DUMMY[0], password) and stored is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(stored: str) -> bool:
    return _hasher.check_needs_rehash(stored)
