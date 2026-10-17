"""The body of GET /ui/api/events (requirements S12.6)."""

import asyncio
import time
from collections.abc import AsyncIterator, Awaitable, Callable

from ..events import KEEPALIVE_SECONDS, STREAM_SECONDS, Broker, Event, Subscriber

# Whether the session is still good, without touching its idle time: None when it is, or why
# it ended ("signed-out", "expired", "disabled").
SessionCheck = Callable[[], Awaitable[str | None]]


async def stream(
    broker: Broker,
    sub: Subscriber,
    hello: dict,
    session_ended: SessionCheck,
    seconds: float = STREAM_SECONDS,
    keepalive: float = KEEPALIVE_SECONDS,
) -> AsyncIterator[bytes]:
    try:
        yield b"retry: 3000\n\n"
        yield Event("hello", hello).encode()
        deadline = time.monotonic() + seconds
        while not sub.closed and not broker.stopping:
            left = deadline - time.monotonic()
            if left <= 0:
                break
            try:
                event = await asyncio.wait_for(sub.queue.get(), timeout=min(keepalive, left))
            except TimeoutError:
                ended = await session_ended()
                if ended:
                    yield Event("session", {"state": ended}).encode()
                    break
                yield b": keepalive\n\n"
                continue
            if event.kind == "closing":
                break
            yield event.encode()
            if event.kind == "session":
                break
    finally:
        broker.unsubscribe(sub)
