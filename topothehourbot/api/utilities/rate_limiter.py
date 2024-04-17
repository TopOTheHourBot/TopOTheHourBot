from __future__ import annotations

__all__ = ["RateLimiter"]

import asyncio
from asyncio import Event, TimerHandle
from collections.abc import Awaitable, Generator
from typing import Any


class RateLimiter(Awaitable[None]):

    __slots__ = ("_count", "_event", "_timer", "_max_count", "_time_off")
    _count: int
    _event: Event
    _timer: TimerHandle | None
    _max_count: int
    _time_off: float

    def __init__(self, max_count: int, *, time_off: float) -> None:
        self._count = 0
        self._event = Event()
        self._event.set()  # Timer is "done" by default
        self._timer = None
        self.max_count = max_count
        self.time_off = time_off

    def __await__(self) -> Generator[Any, None, None]:
        return self.wait().__await__()

    def _on_timer_done(self) -> None:
        self._count = 0
        self._event.set()
        self._timer = None

    @property
    def max_count(self) -> int:
        return self._max_count

    @max_count.setter
    def max_count(self, max_count: int) -> None:
        if max_count <= 0:
            raise ValueError("Maximum count must be a positive integer")
        self._max_count = max_count

    @property
    def time_off(self) -> float:
        return self._time_off

    @time_off.setter
    def time_off(self, time_off: float) -> None:
        self._time_off = time_off

    @property
    def time_remaining(self) -> float | None:
        timer = self._timer
        if timer is None:
            return
        return max(
            timer.when() - asyncio.get_running_loop().time(),
            0,
        )

    async def wait(self) -> None:
        while not self.admit():
            await self._event.wait()

    def admit(self) -> bool:
        count = self._count
        if count == self.max_count:
            return False
        if count == 0:
            loop = asyncio.get_running_loop()
            self._event.clear()
            self._timer = loop.call_at(
                loop.time() + self.time_off,
                self._on_timer_done,
            )
        self._count = count + 1
        return True
