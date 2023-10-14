from __future__ import annotations

__all__ = [
    "RowProtocol",
    "CursorProtocol",
    "SQLStream",
]

from abc import abstractmethod
from collections.abc import (AsyncIterator, Coroutine, Iterable, Iterator,
                             Mapping, Sequence)
from typing import Any, Optional, Protocol, overload, override

from channels import SupportsSend


class RowProtocol(Protocol):

    @abstractmethod
    def __len__(self) -> int:
        raise NotImplementedError

    @overload
    @abstractmethod
    def __getitem__(self, key: str, /) -> Any: ...
    @overload
    @abstractmethod
    def __getitem__(self, key: int, /) -> Any: ...
    @overload
    @abstractmethod
    def __getitem__(self, key: slice, /) -> Sequence[Any]: ...
    @abstractmethod
    def __getitem__(self, key, /):
        raise NotImplementedError

    def __iter__(self) -> Iterator[Any]:
        keys = range(len(self))
        return map(self.__getitem__, keys)

    @abstractmethod
    def keys(self) -> Sequence[str]:
        raise NotImplementedError


class CursorProtocol(Protocol):

    @abstractmethod
    def __aiter__(self) -> AsyncIterator[RowProtocol]:
        raise NotImplementedError

    async def __aenter__(self) -> CursorProtocol:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb, /) -> None:
        await self.close()

    @abstractmethod
    def fetchone(self) -> Coroutine[Any, Any, Optional[RowProtocol]]:
        raise NotImplementedError

    @abstractmethod
    def fetchmany(self, size: Optional[int] = None, /) -> Coroutine[Any, Any, Iterable[RowProtocol]]:
        raise NotImplementedError

    @abstractmethod
    def fetchall(self) -> Coroutine[Any, Any, Iterable[RowProtocol]]:
        raise NotImplementedError

    @abstractmethod
    def close(self) -> Coroutine[Any, Any, Any]:
        raise NotImplementedError


class SQLStream(SupportsSend[str], Protocol):

    @override
    @abstractmethod
    def send(self, expr: str, params: Sequence[object] | Mapping[str, object] = (), /) -> Coroutine[Any, Any, CursorProtocol]:
        raise NotImplementedError

    @abstractmethod
    def commit(self) -> Coroutine[Any, Any, Any]:
        raise NotImplementedError
