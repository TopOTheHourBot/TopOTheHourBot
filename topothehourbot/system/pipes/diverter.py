from __future__ import annotations

__all__ = ["Diverter"]

import uuid
from collections.abc import Collection, Iterator
from contextlib import contextmanager
from typing import Optional, final
from uuid import UUID

from .pipe import Pipe


class Diverter[T]:

    __slots__ = ("_pipes")
    _pipes: dict[UUID, Pipe[T]]

    def __init__(self) -> None:
        self._pipes = {}

    @final
    def pipes(self) -> Collection[Pipe[T]]:
        """Return a view of the currently-attached pipes"""
        return self._pipes.values()

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
