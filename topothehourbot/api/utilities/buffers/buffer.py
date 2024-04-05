from __future__ import annotations

__all__ = ["Buffer"]

import asyncio
from asyncio import Future
from collections import deque as Deque
from collections.abc import AsyncIterator
from typing import Optional, final

from . import stream
from .exceptions import Closure


@final
class Buffer[T]:

    __slots__ = ("_buffer", "_receiver", "_closed")
    _buffer: Deque[T]
    _receiver: Optional[Future[None]]
    _closed: bool

    def __init__(self, max_size: Optional[int] = None) -> None:
        super().__init__()
        self._buffer = Deque((), max_size)
        self._receiver = None
        self._closed = False

    @stream.compose
    async def __aiter__(self) -> AsyncIterator[T]:
        try:
            while True:
                yield await self.recv()
        except Closure:
            return

    def size(self) -> int:
        """The buffer's current size"""
        return len(self._buffer)

    def max_size(self) -> Optional[int]:
        """The buffer's maximum size"""
        return self._buffer.maxlen

    def full(self) -> bool:
        """The buffer's full state"""
        return self.size() == self.max_size()

    def empty(self) -> bool:
        """The buffer's empty state"""
        return self.size() == 0

    def closed(self) -> bool:
        """The buffer's closed state"""
        return self._closed

    def send(self, value: T, /) -> None:
        """Send a value to the buffer

        Discards the oldest value in the buffer buffer to insert the incoming
        one when at maximum size.

        Raises ``Closure`` if the buffer has been closed.
        """
        if self._closed:
            raise Closure
        self._buffer.append(value)
        receiver = self._receiver
        if not (receiver is None or receiver.done()):
            receiver.set_result(None)

    async def recv(self) -> T:
        """Receive a value from the buffer

        Raises ``Closure`` if the buffer has been, or is closed during
        execution.

        Raises ``RuntimeError`` if the buffer is receiving in another
        coroutine.
        """
        if self._closed:
            raise Closure
        if self._receiver is not None:
            raise RuntimeError("Buffer is already receiving")
        loop = asyncio.get_running_loop()
        buffer = self._buffer
        while not buffer:
            receiver = loop.create_future()
            self._receiver = receiver
            try:
                await receiver
            finally:
                self._receiver = None
        return buffer.popleft()

    def open(self) -> None:
        """Open the buffer"""
        self._closed = False

    def close(self) -> None:
        """Close the buffer

        Raises ``Closure`` into the active ``recv()`` call (if one exists).
        """
        self._closed = True
        receiver = self._receiver
        if not (receiver is None or receiver.done()):
            receiver.set_exception(Closure)

    def clear(self) -> None:
        """Clear the buffer

        Discards all values from the buffer.
        """
        self._buffer.clear()
