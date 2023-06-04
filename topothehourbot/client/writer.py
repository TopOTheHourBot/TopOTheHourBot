from __future__ import annotations

from abc import abstractmethod
from typing import Any, Protocol, TypeVar

from websockets.client import WebSocketClientProtocol

from .streams import IStreamBase

__all__ = ["Writer"]

InputT = TypeVar("InputT", contravariant=True)


class Writer(Protocol[InputT]):

    @abstractmethod
    async def __call__(self, istream: IStreamBase[InputT], socket: WebSocketClientProtocol, /) -> Any:
        raise NotImplementedError
