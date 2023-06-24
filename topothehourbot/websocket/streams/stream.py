from __future__ import annotations

import asyncio
import collections
from abc import ABCMeta, abstractmethod
from typing import Generic, TypeVar

T = TypeVar("T")
T_co = TypeVar("T_co", covariant=True)
T_contra = TypeVar("T_contra", contravariant=True)


class IStream(Generic[T_co], metaclass=ABCMeta):

    __slots__ = ()

    @abstractmethod
    async def get(self) -> T_co:
        """Get a value from the stream, waiting for one to become available"""
        raise NotImplementedError


class OStream(Generic[T_contra], metaclass=ABCMeta):

    __slots__ = ()

    @abstractmethod
    async def put(self, value: T_contra, /) -> None:
        """Put ``value`` into the stream, waiting for an appropriate time to do
        so

        Prefer ``put_drop()`` for values with less importance.
        """
        raise NotImplementedError

    @abstractmethod
    def put_drop(self, value: T_contra, /) -> bool:
        """Put ``value`` into the stream instantly, discarding it if not an
        appropriate time to do so at invocation

        Returns true if the ``value`` was placed into the stream, otherwise
        false.

        Prefer ``put()`` for values with more importance.
        """
        raise NotImplementedError


class IOStream(IStream[T], OStream[T], Generic[T]):

    __slots__ = ("_values", "_cooldown", "_last_put_time")
    _values: collections.deque[T]
    _cooldown: float
    _last_put_time: float

    def __init__(self, *, cooldown: float = 0) -> None:
        self._values = collections.deque()
        self._cooldown = cooldown
        self._last_put_time = 0

    @property
    def cooldown(self) -> float:
        """The amount of time, in seconds, to wait before subsequent putting
        operations are allowed to affect the underlying buffer
        """
        return self._cooldown

    @cooldown.setter
    def cooldown(self, cooldown: float) -> None:
        self._cooldown = cooldown

    async def get(self) -> T:
        while not self._values:
            await asyncio.sleep(0)
        return self._values.popleft()

    async def put(self, value: T, /) -> None:
        _, next_put_time, delay = self.timestep()
        self._last_put_time = next_put_time
        await asyncio.sleep(delay)
        self._values.append(value)

    def put_drop(self, value: T, /) -> bool:
        _, next_put_time, delay = self.timestep()
        if delay:
            return False
        self._last_put_time = next_put_time
        self._values.append(value)
        return True

    def timestep(self) -> tuple[float, float, float]:
        """Return a ``(start, stop, step)`` tuple, where ``start`` is the
        current event loop time, ``stop`` is the next available time to put,
        and ``step`` is the amount of time to delay before reaching ``stop``

        All three values of the tuple are guaranteed to be greater than or
        equal to 0.
        """
        curr_put_time = asyncio.get_event_loop().time()
        last_put_time = self._last_put_time
        cooldown = self._cooldown
        delay = max(cooldown - curr_put_time - last_put_time, 0)
        next_put_time = curr_put_time + delay
        return (curr_put_time, next_put_time, delay)
