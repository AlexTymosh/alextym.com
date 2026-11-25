"""In-process, room-scoped wakeups. No storage reads, writes or wire payloads."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from contextlib import suppress


class PublishSignal:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._listeners: dict[str, dict[object, Callable[[], None]]] = {}

    def subscribe(self, room: str, wake: Callable[[], None]) -> Callable[[], None]:
        token = object()
        with self._lock:
            self._listeners.setdefault(room, {})[token] = wake

        def unsubscribe() -> None:
            with self._lock:
                listeners = self._listeners.get(room)
                if listeners is not None:
                    listeners.pop(token, None)
                    if not listeners:
                        self._listeners.pop(room, None)

        return unsubscribe

    def notify(self, room: str) -> None:
        with self._lock:
            listeners = tuple(self._listeners.get(room, {}).values())
        for wake in listeners:
            # A disconnected/closed event loop must not fail a committed command.
            with suppress(RuntimeError):
                wake()


async def wait_for_publish_or_frame(reader: asyncio.Task, wake: asyncio.Event) -> bool:
    """Wake on publish or input; retain the existing 75ms idle timeout."""
    pending_wake = asyncio.create_task(wake.wait())
    try:
        await asyncio.wait(
            {reader, pending_wake}, timeout=0.075, return_when=asyncio.FIRST_COMPLETED
        )
        return reader.done()
    finally:
        pending_wake.cancel()
        with suppress(asyncio.CancelledError):
            await pending_wake
