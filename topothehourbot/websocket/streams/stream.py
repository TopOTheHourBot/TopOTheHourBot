from __future__ import annotations

import asyncio
from abc import ABCMeta, abstractmethod
from collections import deque as Deque
from collections.abc import AsyncIterable, AsyncIterator, Awaitable
from typing import Generic, TypeVar

from .routine import routine

__all__ = [
    "CLOSE_STREAM",
    "IStreamBase",
    "OStreamBase",
    "IOStreamBase",
    "UnboundedIOStream",
    "TimeboundIOStream",
]

CLOSE_STREAM = object()  #: Sentinel value to signal stream closure

T = TypeVar("T")
T_co = TypeVar("T_co", covariant=True)
T_contra = TypeVar("T_contra", contravariant=True)


class IStreamBase(Generic[T_co], metaclass=ABCMeta):

    __slots__ = ()

    @abstractmethod
    async def get(self) -> T_co:
        """Wait and return the next value of the stream

        For the purpose of continuous retrieval, this method can return
        the ``CLOSE_STREAM`` sentinel value to signal that further significant
        values will never be found.
        """
        raise NotImplementedError

    @routine
    async def get_each(self) -> AsyncIterator[T_co]:
        """Return a ``Routine`` that continuously retrieves the next stream
        value until ``CLOSE_STREAM`` is received
        """
        while True:
            value = await self.get()
            if value is CLOSE_STREAM:
                return
            yield value


class OStreamBase(Generic[T_contra], metaclass=ABCMeta):

    __slots__ = ()

    @abstractmethod
    def put(self, value: T_contra, /) -> Awaitable[None]:
        """Wait and place ``value`` into the stream"""
        raise NotImplementedError

    @abstractmethod
    def put_drop(self, value: T_contra, /) -> None:
        """Place ``value`` into the stream, or drop it if at capacity"""
        raise NotImplementedError

    async def put_each(self, values: AsyncIterable[T_contra], /) -> None:
        """Wait and place ``values`` into the stream"""
        async for value in values:
            await self.put(value)

    async def put_drop_each(self, values: AsyncIterable[T_contra], /) -> None:
        """Place or drop ``values`` into the stream"""
        async for value in values:
            self.put_drop(value)


class IOStreamBase(IStreamBase[T_co], OStreamBase[T_contra], Generic[T_co, T_contra], metaclass=ABCMeta):

    __slots__ = ()


class UnboundedIOStream(IOStreamBase[T, T], Generic[T]):

    __slots__ = ("_values")

    _values: Deque[T]

    def __init__(self) -> None:
        self._values = Deque()

    @property
    def size(self) -> int:
        """The current number of values"""
        return len(self._values)

    async def get(self) -> T:
        while not self._values:
            await asyncio.sleep(0)
        return self._values.popleft()

    async def put(self, value: T) -> None:
        self._values.append(value)

    def put_drop(self, value: T) -> None:
        self._values.append(value)


class TimeboundIOStream(UnboundedIOStream[T, T], Generic[T]):

    __slots__ = ("_cooldown", "_prev_put_time")

    _cooldown: float
    _prev_put_time: float

    def __init__(self, cooldown: float = 0) -> None:
        super().__init__()
        self._cooldown = cooldown
        self._prev_put_time = 0

    @property
    def cooldown(self) -> float:
        """The duration of the stream's cooldown period"""
        return self._cooldown

    async def put(self, value: T) -> None:
        curr_put_time = asyncio.get_event_loop().time()
        prev_put_time = self._prev_put_time
        cooldown = self._cooldown

        delay = cooldown - (curr_put_time - prev_put_time)
        await asyncio.sleep(delay)

        await UnboundedIOStream.put(self, value)

        self._prev_put_time = curr_put_time + delay

    def put_drop(self, value: T) -> None:
        curr_put_time = asyncio.get_event_loop().time()
        prev_put_time = self._prev_put_time
        cooldown = self._cooldown

        if (curr_put_time - prev_put_time) <= cooldown:
            return

        UnboundedIOStream.put_drop(self, value)

        self._prev_put_time = curr_put_time
