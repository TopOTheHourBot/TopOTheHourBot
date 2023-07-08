from __future__ import annotations

__all__ = [
    "RecvError",
    "SendError",
    "SupportsRecv",
    "SupportsSend",
    "SupportsRecvAndSend",
]

from abc import abstractmethod
from collections.abc import AsyncIterable, AsyncIterator
from typing import Protocol, TypeVar

from .series import series

T_co = TypeVar("T_co", covariant=True)
T_contra = TypeVar("T_contra", contravariant=True)


class RecvError(Exception):
    """Values can no longer be received"""

    __slots__ = ()


class SendError(Exception):
    """Values can no longer be sent"""

    __slots__ = ()


class SupportsRecv(Protocol[T_co]):
    """Type supports the ``recv()`` and ``recv_each()`` operations"""

    @abstractmethod
    async def recv(self) -> T_co:
        """Receive a value, waiting for one to become available

        This method can raise ``RecvError`` to signal that no further values
        can be received.
        """
        raise NotImplementedError

    @series
    async def recv_each(self) -> AsyncIterator[T_co]:
        """Return an async iterator that continuously receives values until
        ``RecvError``
        """
        try:
            while True:
                yield await self.recv()
        except RecvError:
            return


class SupportsSend(Protocol[T_contra]):
    """Type supports the ``send()`` and ``send_each()`` operations"""

    @abstractmethod
    async def send(self, value: T_contra, /) -> object:
        """Send a value, waiting for an appropriate time to do so

        This method can raise ``SendError`` to signal that no further values
        can be sent.
        """
        raise NotImplementedError

    async def send_each(self, values: AsyncIterable[T_contra], /) -> object:
        """Send values from an async iterable until exhaustion, or until
        ``SendError``
        """
        try:
            async for value in values:
                await self.send(value)
        except SendError:
            return


class SupportsRecvAndSend(SupportsRecv[T_co], SupportsSend[T_contra], Protocol[T_co, T_contra]):
    """Type supports both sending and receiving operations"""
