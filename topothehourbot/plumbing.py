from __future__ import annotations

__all__ = [
    "Pipe",
    "Transport",
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


class Transport(SupportsSend[T_contra], Generic[T_contra, T_co]):

    __slots__ = ("_pipe", "_iostream", "_ostream")
    _pipe: Pipe[T_contra, T_co]
    _iostream: SupportsRecvAndSend[T_contra, T_contra]
    _ostream: SupportsSend[T_co]

    def __init__(
        self,
        pipe: Pipe[T_contra, T_co],
        *,
        iostream: SupportsRecvAndSend[T_contra, T_contra],
        ostream: SupportsSend[T_co],
    ) -> None:
        self._pipe = pipe
        self._iostream = iostream
        self._ostream = ostream

    @property
    def pipe(self) -> Pipe[T_contra, T_co]:
        return self._pipe

    @property
    def iostream(self) -> SupportsRecvAndSend[T_contra, T_contra]:
        return self._iostream

    @property
    def ostream(self) -> SupportsSend[T_co]:
        return self._ostream

    def send(self, value: T_contra, /) -> Coroutine:
        return self._iostream.send(value)

    def ready(self) -> Coroutine:
        return self._pipe(self._iostream, self._ostream)
