from __future__ import annotations

import asyncio
from abc import ABCMeta, abstractmethod
from collections import deque as Deque
from collections.abc import AsyncIterable, AsyncIterator
from typing import Generic, Optional, TypeVar

from .routine import routine

__all__ = [
    "CloseStream",
    "IStreamBase",
    "OStreamBase",
    "IOStreamBase",
    "UnboundedIOStream",
    "IOStream",
    "TimeboundIOStream",
]

T = TypeVar("T")
T_co = TypeVar("T_co", covariant=True)
T_contra = TypeVar("T_contra", contravariant=True)


class CloseStream(Exception):
    """Input stream has no further values to yield"""

    __slots__ = ()


class IStreamBase(Generic[T_co], metaclass=ABCMeta):

    __slots__ = ()

    @abstractmethod
    async def get(self) -> T_co:
        """Wait and return the next value of the stream

        For the purpose of continuous retrieval, this method can raise
        ``CloseStream`` to signal that further values will never be found.
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
    def put(self, value: T_contra, /) -> object:
        """Immediately place ``value`` into the stream"""
        raise NotImplementedError

    async def put_each(self, values: AsyncIterable[T_contra], /) -> object:
        """Immediately place awaited values from ``AsyncIterable`` into the
        stream
        """
        async for value in values:
            self.put(value)


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

    def put(self, value: T) -> object:
        self._values.append(value)


class IOStream(UnboundedIOStream[T, T], Generic[T]):

    __slots__ = ()

    def __init__(self, capacity: Optional[int] = None) -> None:
        self._values = Deque(maxlen=capacity)

    @property
    def capacity(self) -> Optional[int]:
        """The maximum number of values"""
        return self._values.maxlen


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

    def put(self, value: T) -> bool:
        """Immediately place ``value`` into the stream if not within the
        stream's cooldown period

        Returns true if placed into the stream, otherwise false.
        """
        loop = asyncio.get_event_loop()
        next_put_time = loop.time()
        prev_put_time = self._prev_put_time
        if (next_put_time - prev_put_time) <= self._cooldown:
            return False
        super().put(value)
        self._prev_put_time = next_put_time
        return True
