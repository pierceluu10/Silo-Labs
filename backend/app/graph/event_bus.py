from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextvars import ContextVar
from typing import Any

_SENTINEL: Any = object()
_current_bus: ContextVar["EventBus | None"] = ContextVar("silo_event_bus", default=None)


class EventBus:
    """Asyncio-queue-backed fan-out for pipeline events.

    One bus per pipeline run. Nodes emit via `bus.emit({...})`; the transport
    drains via `async for ev in bus.aiter()` and closes with `bus.close()`.
    """

    def __init__(self) -> None:
        self._q: asyncio.Queue[Any] = asyncio.Queue()
        self._closed = False

    def emit(self, event: dict) -> None:
        if self._closed:
            return
        self._q.put_nowait(event)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._q.put_nowait(_SENTINEL)

    async def aiter(self) -> AsyncIterator[dict]:
        while True:
            item = await self._q.get()
            if item is _SENTINEL:
                return
            yield item


def set_bus(bus: EventBus | None) -> None:
    _current_bus.set(bus)


def get_bus() -> EventBus | None:
    return _current_bus.get()


def emit(event: dict) -> None:
    bus = _current_bus.get()
    if bus is not None:
        bus.emit(event)
