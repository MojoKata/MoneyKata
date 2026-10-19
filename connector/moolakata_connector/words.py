"""The vault's 12 words (requirements S18.3.1): 128 bits as 12 words from the BIP39 English
list, the last carrying a 4-bit checksum. The same way MoolaKata writes its keys down, with
its own copy of the list, since the connector imports nothing from MoolaKata."""

import hashlib
from functools import cache
from pathlib import Path

WORDS_FILE = Path(__file__).with_name("bip39-english.txt")
WORDS_SHA256 = "2f5eed53a4727b4bf8880d8f3f199efc90e58503646d9ff8eff3a2ed3b24dbda"


class PhraseError(ValueError):
    pass


@cache
def wordlist() -> tuple[str, ...]:
    data = WORDS_FILE.read_bytes()
    if hashlib.sha256(data).hexdigest() != WORDS_SHA256:
        raise RuntimeError("the shipped BIP39 word list has been changed")
    return tuple(data.decode().split())


@cache
def _by_prefix() -> dict[str, int]:
    return {w[:4]: i for i, w in enumerate(wordlist())}


def to_words(key: bytes) -> list[str]:
    if len(key) != 16:
        raise ValueError("a phrase holds exactly 128 bits")
    checksum = hashlib.sha256(key).digest()[0] >> 4
    bits = (int.from_bytes(key) << 4) | checksum
    return [wordlist()[(bits >> (11 * (11 - i))) & 0x7FF] for i in range(12)]


def from_words(text: str | list[str]) -> bytes:
    """A word may be cut to its first four letters; a wrong word or checksum is refused."""
    tokens = text.lower().split() if isinstance(text, str) else [t.lower() for t in text]
    if len(tokens) != 12:
        raise PhraseError(f"a phrase has 12 words, not {len(tokens)}")
    bits = 0
    for n, token in enumerate(tokens, 1):
        i = _by_prefix().get(token[:4])
        if i is None or not wordlist()[i].startswith(token):
            raise PhraseError(f"word {n} ({token!r}) is not in the word list")
        bits = (bits << 11) | i
    key = (bits >> 4).to_bytes(16)
    if bits & 0xF != hashlib.sha256(key).digest()[0] >> 4:
        raise PhraseError("the words do not check out: one of them is probably wrong")
    return key
