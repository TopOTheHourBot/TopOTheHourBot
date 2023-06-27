from __future__ import annotations

import asyncio
from collections import deque
from typing import Generic, Optional, TypeVar

from .protocols import SupportsRecv, SupportsRecvAndSend, SupportsSend

__all__ = [
    "SendOnlyChannel",
    "Channel",
]

T = TypeVar("T")
T_co = TypeVar("T_co", covariant=True)
T_contra = TypeVar("T_contra", contravariant=True)


class SendOnlyBuffer(SupportsSend[T_contra], Generic[T_contra]):

    __slots__ = ("_values")
    _values: deque[T_contra]

    def __init__(self) -> None:
        self._values = deque()

    async def send(self, value: T_contra, /) -> None:
        self._values.append(value)


class Buffer(SendOnlyBuffer[T], SupportsRecv[T], Generic[T]):

    __slots__ = ()

    async def recv(self) -> T:
        while not self._values:
            await asyncio.sleep(0)
        return self._values.popleft()


class SendOnlyChannel(SupportsSend[T_contra], Generic[T_contra]):

    __slots__ = ("_link", "_cooldown", "_prev_send_time")
    _link: SupportsSend[T_contra]
    _cooldown: float
    _prev_send_time: float

    def __init__(self, link: Optional[SupportsSend[T_contra]] = None, *, cooldown: float = 0) -> None:
        self._link = SendOnlyBuffer() if link is None else link
        self._cooldown = cooldown
        self._prev_send_time = 0

    @property
    def cooldown(self) -> float:
        """The amount of time, in seconds, to wait before subsequent sending
        operations are allowed to be dispatched
        """
        return self._cooldown

    @cooldown.setter
    def cooldown(self, cooldown: float) -> None:
        self._cooldown = cooldown

    async def send(self, value: T_contra, /) -> None:
        curr_send_time, next_send_time, delay = self.wait_span()
        self._prev_send_time = next_send_time
        await asyncio.sleep(delay)
        await self._link.send(value)

    def wait_span(self) -> tuple[float, float, float]:
        """Return a ``(start, stop, step)`` tuple, where ``start`` is the
        current event loop time, ``stop`` is the next available time to send,
        and ``step`` is the amount of time to delay before reaching ``stop``
        """
        curr_send_time = asyncio.get_event_loop().time()
        prev_send_time = self._prev_send_time
        cooldown = self._cooldown
        delay = max(cooldown - curr_send_time - prev_send_time, 0)
        next_send_time = curr_send_time + delay
        return (curr_send_time, next_send_time, delay)


class Channel(SendOnlyChannel[T_contra], SupportsRecv[T_co], Generic[T_co, T_contra]):

    __slots__ = ()
    _link: SupportsRecvAndSend[T_co, T_contra]

    def __init__(self, link: Optional[SupportsRecvAndSend[T_co, T_contra]] = None, *, cooldown: float = 0) -> None:
        super().__init__(link=Buffer() if link is None else link, cooldown=cooldown)

    async def recv(self) -> T_co:
        return await self._link.recv()
