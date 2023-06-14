from __future__ import annotations

import asyncio
from abc import ABCMeta, abstractmethod
from collections import deque as Deque
from collections.abc import AsyncIterable, AsyncIterator, Iterable
from typing import Generic, TypeVar

from websockets.client import WebSocketClientProtocol

from ..ircv3 import IRCv3Package
from .routine import routine

__all__ = [
    "CloseStream",
    "IStreamBase",
    "OStreamBase",
    "IOStreamBase",
    "UnboundIOStream",
    "UnboundIRCv3IOStream",
    "TimeboundIOStream",
    "TimeboundIRCv3IOStream",
]

T = TypeVar("T")
T_co = TypeVar("T_co", covariant=True)
T_contra = TypeVar("T_contra", contravariant=True)


class CloseStream(Exception):

    __slots__ = ()


class IStreamBase(Generic[T_co], metaclass=ABCMeta):

    __slots__ = ()

    @abstractmethod
    async def get(self) -> T_co:
        """Wait and return the next value of the stream

        For the purpose of continuous retrieval, this method can raise
        ``CloseStream`` to signal that further significant values will never be
        found.
        """
        raise NotImplementedError

    @routine
    async def get_each(self) -> AsyncIterator[T_co]:
        """Return a ``Routine`` that continuously retrieves the next stream
        value until ``CloseStream`` is raised
        """
        try:
            while True:
                yield await self.get()
        except CloseStream:
            return


class OStreamBase(Generic[T_contra], metaclass=ABCMeta):

    __slots__ = ()

    @abstractmethod
    async def put(self, value: T_contra, /) -> None:
        """Wait and place ``value`` into the stream"""
        raise NotImplementedError

    async def put_each(self, values: AsyncIterable[T_contra], /) -> None:
        """Wait and place ``values`` into the stream"""
        async for value in values:
            await self.put(value)


class IOStreamBase(IStreamBase[T_co], OStreamBase[T_contra], Generic[T_co, T_contra], metaclass=ABCMeta):

    __slots__ = ()


class UnboundIOStream(IOStreamBase[T, T], Generic[T]):

    __slots__ = ("_values")
    _values: Deque[T]

    def __init__(self, values: Iterable[T] = ()) -> None:
        self._values = Deque(values)

    async def get(self) -> T:
        while not self._values:
            await asyncio.sleep(0)
        return self._values.popleft()

    async def put(self, value: T) -> None:
        self._values.append(value)


class UnboundIRCv3IOStream(IOStreamBase[IRCv3Package, IRCv3Package]):

    __slots__ = ("_socket")
    _socket: WebSocketClientProtocol

    def __init__(self, socket: WebSocketClientProtocol) -> None:
        self._socket = socket

    async def get(self) -> IRCv3Package:
        return IRCv3Package.from_data(await self._socket.recv())

    async def put(self, package: IRCv3Package) -> None:
        await self._socket.send(package.to_data())


class TimeboundIOStreamWrapper(IOStreamBase[T, T], Generic[T]):

    __slots__ = ("_stream", "_cooldown", "_last_put_time")
    _stream: IOStreamBase[T, T]
    _cooldown: float
    _last_put_time: float

    @property
    def cooldown(self) -> float:
        """The duration of the stream's cooldown period"""
        return self._cooldown

    async def get(self) -> T:
        return await self._stream.get()

    async def put(self, value: T) -> None:
        curr_put_time = asyncio.get_event_loop().time()
        last_put_time = self._last_put_time
        cooldown = self._cooldown

        # It's important to set last_put_time before sleeping, otherwise a
        # quickly-following call to put() will calculate delay based on an
        # already "claimed" timestamp

        delay = max(cooldown - (curr_put_time - last_put_time), 0)
        self._last_put_time = curr_put_time + delay

        await asyncio.sleep(delay)
        await self._stream.put(value)


class TimeboundIOStream(TimeboundIOStreamWrapper[T]):

    __slots__ = ()

    def __init__(self, values: IOStreamBase[T, T] | Iterable[T] = (), *, cooldown: float = 0) -> None:
        if isinstance(values, IOStreamBase):
            self._stream = values
        else:
            self._stream = UnboundIOStream(values)
        self._cooldown = cooldown
        self._last_put_time = 0


class TimeboundIRCv3IOStream(TimeboundIOStreamWrapper[IRCv3Package]):

    __slots__ = ()
    _stream: UnboundIRCv3IOStream

    def __init__(self, socket: WebSocketClientProtocol, *, cooldown: float = 0) -> None:
        self._stream = UnboundIRCv3IOStream(socket)
        self._cooldown = cooldown
        self._last_put_time = 0
