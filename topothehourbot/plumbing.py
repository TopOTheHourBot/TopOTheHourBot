from __future__ import annotations

__all__ = [
    "Pipe",
    "Pipeline",
]

from abc import abstractmethod
from collections.abc import Coroutine
from typing import Generic, Protocol, TypeVar

from channels import SupportsRecv, SupportsRecvAndSend, SupportsSend

T_co = TypeVar("T_co", covariant=True)
T_contra = TypeVar("T_contra", contravariant=True)


class Pipe(Protocol[T_contra, T_co]):

    @abstractmethod
    def __call__(self, istream: SupportsRecv[T_contra], ostream: SupportsSend[T_co], /) -> Coroutine:
        raise NotImplementedError


class Pipeline(SupportsSend[T_contra], Generic[T_contra, T_co]):

    __slots__ = ("_pipe", "_istream", "_ostream")
    _pipe: Pipe[T_contra, T_co]
    _istream: SupportsRecvAndSend[T_contra, T_contra]
    _ostream: SupportsSend[T_co]

    def __init__(
        self,
        pipe: Pipe[T_contra, T_co],
        istream: SupportsRecvAndSend[T_contra, T_contra],
        ostream: SupportsSend[T_co],
    ) -> None:
        self._pipe = pipe
        self._istream = istream
        self._ostream = ostream

    @property
    def pipe(self) -> Pipe[T_contra, T_co]:
        return self._pipe

    @property
    def istream(self) -> SupportsRecvAndSend[T_contra, T_contra]:
        return self._istream

    @property
    def ostream(self) -> SupportsSend[T_co]:
        return self._ostream

    def send(self, value: T_contra, /) -> Coroutine:
        return self._istream.send(value)

    def join(self) -> Coroutine:
        return self._pipe(self._istream, self._ostream)
