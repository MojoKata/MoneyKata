"""Rate limits (requirements §16.7.5), answered with 429 and Retry-After. Counters live in
memory: they are work state, not records (schema.md §4.4), and a restart clears them."""

import math
import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable

from .errors import Problem


class Window:
    """At most `limit` events per `seconds` for each key."""

    def __init__(self, limit: int, seconds: float, clock: Callable[[], float] = time.monotonic):
        self.limit = limit
        self.seconds = seconds
        self._clock = clock
        self._seen: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def _trim(self, q: deque, now: float) -> None:
        while q and now - q[0] >= self.seconds:
            q.popleft()

    def hit(self, key: str) -> float:
        """Count one event; returns 0, or the seconds to wait when over the limit."""
        with self._lock:
            now = self._clock()
            q = self._seen[key]
            self._trim(q, now)
            if len(q) >= self.limit:
                return self.seconds - (now - q[0])
            q.append(now)
            return 0.0

    def count(self, key: str) -> int:
        with self._lock:
            q = self._seen.get(key)
            if not q:
                return 0
            self._trim(q, self._clock())
            return len(q)

    def clear(self, key: str) -> None:
        with self._lock:
            self._seen.pop(key, None)

    def check(self, key: str, what: str) -> None:
        wait = self.hit(key)
        if wait:
            raise too_many(wait, what)


def too_many(wait: float, what: str) -> Problem:
    return Problem(
        429,
        "rate-limited",
        f"Too many {what}. Try again in a moment.",
        headers={"Retry-After": str(max(1, math.ceil(wait)))},
    )


class SignInGuard:
    """Ten failures in 15 minutes lock that username for 15 minutes and slow that address
    (§16.7.5.1, §13.1). Lockout length and threshold come from Settings."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._failures: dict[str, deque] = defaultdict(deque)
        self._locked_until: dict[str, float] = {}
        self._address = Window(10, 15 * 60, clock)
        self._lock = threading.Lock()

    def locked(self, username: str) -> float:
        """Seconds the username stays locked, or 0."""
        with self._lock:
            until = self._locked_until.get(username.lower(), 0)
            left = until - self._clock()
            return left if left > 0 else 0.0

    def address_delay(self, address: str) -> float:
        """A pause before answering an address that keeps failing."""
        n = self._address.count(address)
        return 0.0 if n < 10 else min(5.0, 0.5 * (n - 9))

    def failed(
        self, username: str, address: str, threshold: int = 10, lock_minutes: int = 15
    ) -> bool:
        """Record a failure; True when it locks the username."""
        self._address.hit(address)
        key = username.lower()
        with self._lock:
            now = self._clock()
            q = self._failures[key]
            while q and now - q[0] >= 15 * 60:
                q.popleft()
            q.append(now)
            if len(q) >= threshold:
                self._locked_until[key] = now + lock_minutes * 60
                q.clear()
                return True
            return False

    def succeeded(self, username: str) -> None:
        with self._lock:
            self._failures.pop(username.lower(), None)
            self._locked_until.pop(username.lower(), None)
