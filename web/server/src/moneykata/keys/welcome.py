"""The welcome's phrases (requirements S15.4.4): on a new server, every visit to the welcome
makes a new master key and shows its phrase, held in this process's memory only, and the one
whose words are typed back becomes the key. A phrase that is never confirmed is never written,
so whoever only looked at one knows nothing of the key the server keeps."""

import secrets
import threading
import time
from dataclasses import dataclass, field

from . import master

LIFE = 60 * 60  # an hour to write the words down and type three back
KEEP = 20  # phrases on offer at once; a new one past these drops the oldest


@dataclass(frozen=True)
class Offer:
    key: bytes
    picks: tuple[int, ...]  # the word positions (0-based) to be typed back
    made: float = field(default_factory=time.monotonic)


class Phrases:
    """The phrases on offer, each under a random token its browser holds."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._offers: dict[str, Offer] = {}

    def offer(self) -> tuple[str, Offer]:
        token = secrets.token_urlsafe(32)
        picks = tuple(sorted(secrets.SystemRandom().sample(range(12), 3)))
        made = Offer(master.new_master(), picks)
        with self._lock:
            self._expire()
            while len(self._offers) >= KEEP:
                self._offers.pop(next(iter(self._offers)))
            self._offers[token] = made
        return token, made

    def get(self, token: str) -> Offer | None:
        with self._lock:
            self._expire()
            return self._offers.get(token)

    def clear(self) -> None:
        """Once a key is made, every other phrase on offer goes."""
        with self._lock:
            self._offers.clear()

    def _expire(self) -> None:
        now = time.monotonic()
        for token in [t for t, o in self._offers.items() if now - o.made > LIFE]:
            del self._offers[token]
