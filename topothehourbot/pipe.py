from __future__ import annotations

__all__ = ["Pipe"]

from abc import abstractmethod
from collections.abc import Coroutine
from typing import Protocol

from channels import SupportsRecv, SupportsSend
from ircv3 import IRCv3Command


class Pipe(Protocol):

    @abstractmethod
    def __call__(self, istream: SupportsRecv[IRCv3Command], ostream: SupportsSend[IRCv3Command], /) -> Coroutine:
        raise NotImplementedError
