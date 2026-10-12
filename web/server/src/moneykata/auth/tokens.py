"""Session, invitation, reset and confirmation tokens: 256 random bits, stored only as their
SHA-256 (requirements §17.4, §18.1.6)."""

import hashlib
import secrets


def new_token() -> tuple[str, str]:
    """A token for the browser or an email, and the hash to store."""
    token = secrets.token_urlsafe(32)
    return token, digest(token)


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
