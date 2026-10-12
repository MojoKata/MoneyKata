"""The live stream (requirements §15.6): one Server-Sent Events stream per open page. It
carries what changed (a kind and a fingerprint or count), never data: the screen reloads
through its usual routes, which apply the caller's shares.

Background tasks run in threads, so `publish` may be called from any thread.
"""

import asyncio
import contextlib
import json
import logging
import threading
from collections.abc import Iterable
from dataclasses import dataclass, field

log = logging.getLogger("moneykata.events")

STREAM_SECONDS = 4 * 60
KEEPALIVE_SECONDS = 20


@dataclass(frozen=True)
class Event:
    kind: str
    data: dict = field(default_factory=dict)

    def encode(self) -> bytes:
        return f"event: {self.kind}\ndata: {json.dumps(self.data, sort_keys=True)}\n\n".encode()


@dataclass(eq=False)
class Subscriber:
    user_id: str
    session_hash: str
    queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=256))
    closed: bool = False


class Broker:
    def __init__(self) -> None:
        self._subs: set[Subscriber] = set()
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self.stopping = False

    def bind(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def subscribe(self, user_id: str, session_hash: str) -> Subscriber:
        sub = Subscriber(user_id, session_hash)
        with self._lock:
            self._subs.add(sub)
        return sub

    def unsubscribe(self, sub: Subscriber) -> None:
        with self._lock:
            self._subs.discard(sub)

    def _deliver(
        self, event: Event, users: frozenset[str] | None, session_hash: str | None
    ) -> None:
        with self._lock:
            subs = list(self._subs)
        for sub in subs:
            if users is not None and sub.user_id not in users:
                continue
            if session_hash is not None and sub.session_hash != session_hash:
                continue
            try:
                sub.queue.put_nowait(event)
            except asyncio.QueueFull:
                # A page that stopped reading: end its stream; the browser reconnects.
                sub.closed = True

    def publish(
        self,
        kind: str,
        data: dict | None = None,
        users: Iterable[str] | None = None,
        session_hash: str | None = None,
    ) -> None:
        """Tell every stream (or those of the users named) that something changed."""
        event = Event(kind, data or {})
        audience = None if users is None else frozenset(users)
        loop = self._loop
        if loop is None:
            return
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is loop:
            self._deliver(event, audience, session_hash)
        elif not loop.is_closed():
            with contextlib.suppress(RuntimeError):  # the loop closed as the server stopped
                loop.call_soon_threadsafe(self._deliver, event, audience, session_hash)

    def end_session(self, session_hash: str, reason: str) -> None:
        """A session ended (signed out, disabled): its streams say so and close."""
        self.publish("session", {"state": reason}, session_hash=session_hash)

    def end_user(self, user_id: str, reason: str) -> None:
        self.publish("session", {"state": reason}, users=[user_id])

    async def close_all(self) -> None:
        """On stopping: every stream ends, so requests in flight can finish (§16.6)."""
        self.stopping = True
        with self._lock:
            subs = list(self._subs)
        for sub in subs:
            sub.closed = True
            with contextlib.suppress(asyncio.QueueFull):
                sub.queue.put_nowait(Event("closing"))

    def count(self) -> int:
        with self._lock:
            return len(self._subs)
