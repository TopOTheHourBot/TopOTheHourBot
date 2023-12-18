from __future__ import annotations

__all__ = [
    "Assembly",
    "Diverter",
]

import uuid
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import Optional, Self, final
from uuid import UUID

from .pipe import Closure, Pipe


class Assembly[T]:

    __slots__ = ("_pipes")
    _pipes: dict[UUID, Pipe[T]]

    def __init__(self) -> None:
        self._pipes = {}

    @final
    def pipes(self) -> Mapping[UUID, Pipe[T]]:
        """Return a view of the currently-attached pipes"""
        return self._pipes

    @final
    def attach(self, pipe: Pipe[T]) -> UUID:
        """Attach ``pipe`` and return its assigned token"""
        token = uuid.uuid4()
        self._pipes[token] = pipe
        return token

    @final
    def detach(self, token: UUID) -> bool:
        """Detach the pipe assigned to ``token``, returning true if a
        corresponding pipe was found, otherwise false
        """
        try:
            del self._pipes[token]
        except KeyError:
            return False
        else:
            return True

    @final
    @contextmanager
    def attachment(self, pipe: Optional[Pipe[T]] = None) -> Iterator[Pipe[T]]:
        """Return a context manager that safely attaches and detaches ``pipe``

        Default-constructs a ``Pipe`` instance if ``pipe`` is ``None``.
        """
        if pipe is None:
            pipe = Pipe()
        token = self.attach(pipe)
        try:
            yield pipe
        finally:
            self.detach(token)


class Diverter[T](Assembly[T]):

    __slots__ = ()

    def send(self, value: T, /) -> None:
        """Send a value to all attached pipes

        Pipes that are closed but still attached at the moment of sending are
        detached.
        """
        tokens = []
        for token, pipe in self.pipes().items():
            try:
                pipe.send(value)
            except Closure:
                tokens.append(token)
        for token in tokens:
            self.detach(token)

    def close(self) -> None:
        """Close and detach all attached pipes"""
        tokens = []
        for token, pipe in self.pipes().items():
            pipe.close()
            tokens.append(token)
        for token in tokens:
            self.detach(token)

    def clear(self) -> None:
        """Clear all attached pipes"""
        for pipe in self.pipes().values():
            pipe.clear()

    @contextmanager
    def closure(self) -> Iterator[Self]:
        """Return a context manager that ensures the diverter's closure upon
        exit
        """
        try:
            yield self
        finally:
            self.close()
