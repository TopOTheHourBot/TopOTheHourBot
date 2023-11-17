from __future__ import annotations

__all__ = [
    "Closure",
    "Pipe",
]

import asyncio
from asyncio import Future, InvalidStateError
from collections import deque as Deque
from collections.abc import AsyncIterator
from typing import Optional, final

from .series import Series


class Closure(Exception):
    """Pipe has been closed"""

    __slots__ = ()


@final
class Pipe[T]:

    __slots__ = ("_buffer", "_receiver", "_closer")
    _buffer: Deque[T]
    _receiver: Optional[Future[None]]
    _closer: Future[None]

    def __init__(self, max_size: Optional[int] = None) -> None:
        self._buffer = Deque((), max_size)
        self._receiver = None
        self._closer = asyncio.get_running_loop().create_future()

    @Series.from_generator
    async def __aiter__(self) -> AsyncIterator[T]:
        try:
            while True:
                yield await self.recv()
        except Closure:
            return

    def send(self, value: T, /) -> None:
        """Send a value to the pipe

        Discards the oldest value in the pipe buffer to insert the incoming
        one when at maximum size.

        Raises ``Closure`` if the pipe has been closed.
        """
        if self.is_closed():
            raise Closure
        self._buffer.append(value)
        if (receiver := self._receiver):
            receiver.set_result(None)

    async def recv(self) -> T:
        """Receive a value from the pipe

        Raises ``Closure`` if the pipe has been closed, or ``RuntimeError``
        if the pipe is receiving in another coroutine.
        """
        if self.is_closed():
            raise Closure
        if self._receiver is not None:
            raise RuntimeError("pipe is already receiving")
        buffer = self._buffer
        while not buffer:
            receiver = asyncio.get_running_loop().create_future()
            self._receiver = receiver
            try:
                await receiver
            finally:
                self._receiver = None
        return buffer.popleft()

    def close(self) -> None:
        """Close the pipe

        Raises ``Closure`` into the active ``recv()`` call, if one exists.
        """
        try:
            self._closer.set_result(None)
        except InvalidStateError:
            return
        if (receiver := self._receiver):
            receiver.set_exception(Closure)

    def clear(self) -> None:
        """Clear the pipe

        Discards all values from the pipe buffer.
        """
        self._buffer.clear()

    def is_closed(self) -> bool:
        """Return true if the pipe has been closed, otherwise false"""
        return self._closer.done()
