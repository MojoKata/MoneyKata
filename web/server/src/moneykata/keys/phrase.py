"""Recovery phrases (requirements §18.6.1, §14.9.2): 128 bits written as 12 words from the
BIP39 English list, the last word carrying a 4-bit checksum. The words are only a way to
write a key down; BIP39's wallet derivation is never applied to them."""

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
    """Each word is recognised by its first four letters (shorter words in full)."""
    return {w[:4]: i for i, w in enumerate(wordlist())}


def to_words(key: bytes) -> list[str]:
    if len(key) != 16:
        raise ValueError("a recovery phrase holds exactly 128 bits")
    checksum = hashlib.sha256(key).digest()[0] >> 4
    bits = (int.from_bytes(key) << 4) | checksum
    words = wordlist()
    return [words[(bits >> (11 * (11 - i))) & 0x7FF] for i in range(12)]


def from_words(text: str | list[str]) -> bytes:
    """The key from its 12 words, typed with any case or spacing; a word may be cut to its
    first four letters. A wrong word or a failed checksum is refused."""
    tokens = text.lower().split() if isinstance(text, str) else [t.lower() for t in text]
    if len(tokens) != 12:
        raise PhraseError(f"a recovery phrase has 12 words, not {len(tokens)}")
    index = _by_prefix()
    bits = 0
    for n, token in enumerate(tokens, 1):
        i = index.get(token[:4])
        if i is None or not wordlist()[i].startswith(token):
            raise PhraseError(f"word {n} ({token!r}) is not in the word list")
        bits = (bits << 11) | i
    key = (bits >> 4).to_bytes(16)
    if bits & 0xF != hashlib.sha256(key).digest()[0] >> 4:
        raise PhraseError("the words do not check out: one of them is probably wrong")
    return key
