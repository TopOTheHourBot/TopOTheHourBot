from __future__ import annotations

from abc import abstractmethod
from typing import Any, Protocol, TypeVar

from .streams import IStreamBase, OStreamBase

__all__ = ["Reader"]

InputT = TypeVar("InputT", contravariant=True)
OutputT = TypeVar("OutputT", covariant=True)


class Reader(Protocol[InputT, OutputT]):

    @abstractmethod
    async def __call__(self, istream: IStreamBase[InputT], ostream: OStreamBase[OutputT], /) -> Any:
        raise NotImplementedError
