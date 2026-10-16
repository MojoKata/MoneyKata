"""Rate limits (requirements S13.7.5), answered with 429 and Retry-After. Counters live in
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
    """Ten failures in 15 minutes lock the **address** they came from for 15 minutes, and a
    username that keeps failing is **slowed**, never locked, so nobody can lock an admin out by
    typing wrong passwords (S13.7.5.1, S10.1). Lockout length and threshold come from
    Settings."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._failures: dict[str, deque] = defaultdict(deque)  # by address
        self._by_user: dict[str, deque] = defaultdict(deque)
        self._locked_until: dict[str, float] = {}  # by address
        self._lock = threading.Lock()

    def _trim(self, q: deque, now: float) -> None:
        while q and now - q[0] >= 15 * 60:
            q.popleft()

    def locked(self, address: str) -> float:
        """Seconds the address stays locked, or 0."""
        with self._lock:
            until = self._locked_until.get(address, 0)
            left = until - self._clock()
            return left if left > 0 else 0.0

    def delay(self, username: str, address: str) -> float:
        """A pause before answering for a username that keeps failing, from anywhere: half a
        second per failure past the third, up to five seconds."""
        with self._lock:
            q = self._by_user[username.lower()]
            self._trim(q, self._clock())
            n = len(q)
        return 0.0 if n < 3 else min(5.0, 0.5 * (n - 2))

    def succeeded(self, username: str) -> None:
        """A sign-in: the username's failures are forgotten, so it is no longer slowed."""
        with self._lock:
            self._by_user.pop(username.lower(), None)

    def failed(
        self, username: str, address: str, threshold: int = 10, lock_minutes: int = 15
    ) -> bool:
        """Record a failure; True when it locks the address."""
        with self._lock:
            now = self._clock()
            u = self._by_user[username.lower()]
            self._trim(u, now)
            u.append(now)
            q = self._failures[address]
            self._trim(q, now)
            q.append(now)
            if len(q) >= threshold:
                self._locked_until[address] = now + lock_minutes * 60
                q.clear()
                return True
            return False
