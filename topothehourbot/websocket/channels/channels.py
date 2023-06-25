from __future__ import annotations

import asyncio
import collections
from typing import Generic, Optional, TypeVar

from websockets.client import WebSocketClientProtocol
from websockets.exceptions import ConnectionClosed
from websockets.typing import Data

from ..ircv3 import IRCv3Package
from .protocols import (RecvError, SendError, SupportsRecv,
                        SupportsRecvAndSend, SupportsSend)

__all__ = [
    "IRCv3Channel",
    "SendingChannel",
    "Channel",
]

T = TypeVar("T")
T_co = TypeVar("T_co", covariant=True)
T_contra = TypeVar("T_contra", contravariant=True)


class IRCv3Channel(SupportsRecvAndSend[IRCv3Package, IRCv3Package | Data]):

    __slots__ = ("_socket")
    _socket: WebSocketClientProtocol

    def __init__(self, socket: WebSocketClientProtocol, /) -> None:
        self._socket = socket

    async def recv(self) -> IRCv3Package:
        try:
            string = await self._socket.recv()
            assert isinstance(string, str)
            return IRCv3Package.from_string(string)
        except ConnectionClosed as exc:
            raise RecvError from exc

    async def send(self, value: IRCv3Package | Data, /) -> None:
        try:
            if isinstance(value, IRCv3Package):
                string = value.into_string()
            else:
                string = value
            await self._socket.send(string)
        except ConnectionClosed as exc:
            raise SendError from exc


class SendingBuffer(SupportsSend[T_contra], Generic[T_contra]):

    __slots__ = ("_values")
    _values: collections.deque[T_contra]

    def __init__(self) -> None:
        self._values = collections.deque()

    async def send(self, value: T_contra, /) -> None:
        self._values.append(value)


class Buffer(SendingBuffer[T], SupportsRecv[T], Generic[T]):

    __slots__ = ()

    async def recv(self) -> T:
        while not self._values:
            await asyncio.sleep(0)
        return self._values.popleft()


class SendingChannel(SupportsSend[T_contra], Generic[T_contra]):

    __slots__ = ("_linked_channel", "_cooldown", "_prev_send_time")
    _linked_channel: SupportsSend[T_contra]
    _cooldown: float
    _prev_send_time: float

    def __init__(self, linked_channel: Optional[SupportsSend[T_contra]] = None, *, cooldown: float = 0) -> None:
        self._linked_channel = SendingBuffer() if linked_channel is None else linked_channel
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
        await self._linked_channel.send(value)

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


class Channel(SendingChannel[T_contra], SupportsRecv[T_co], Generic[T_co, T_contra]):

    __slots__ = ()
    _linked_channel: SupportsRecvAndSend[T_co, T_contra]

    def __init__(self, linked_channel: Optional[SupportsRecvAndSend[T_co, T_contra]] = None, *, cooldown: float = 0) -> None:
        super().__init__(linked_channel=Buffer() if linked_channel is None else linked_channel, cooldown=cooldown)

    async def recv(self) -> T_co:
        return await self._linked_channel.recv()
