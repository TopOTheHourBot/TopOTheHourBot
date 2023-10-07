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
    """Protocol for callable, asynchronous objects that take an input and
    output stream as arguments - a "pipe"
    """

    @abstractmethod
    def __call__(self, istream: SupportsRecv[T_contra], ostream: SupportsSend[T_co], /) -> Coroutine:
        raise NotImplementedError


class Transport(SupportsSend[T_contra], Generic[T_contra, T_co]):
    """A thin wrapper around a ``Pipe`` and its input and output stream

    Note that this class does not perform any kind of task management or
    execution - it is simply used as a means to group pipes alongside their
    streams for easier object consolidation. It is up to the API user to begin
    data flow in however they see fit.

    Transports are a type of output stream, and thus supports the ``send()``
    and ``send_each()`` operations. Sends are simply forwarded to the
    underlying ``iostream``, which is interpreted as the input stream to
    ``pipe``.
    """

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
        """Send a value to ``iostream``"""
        return self._iostream.send(value)

    def ready(self) -> Coroutine:
        """Call ``pipe`` with ``iostream`` as its input, and ``ostream`` as its
        output
        """
        return self._pipe(self._iostream, self._ostream)
