from __future__ import annotations

__all__ = ["Pipe"]

from abc import abstractmethod
from collections.abc import Coroutine
from typing import Protocol

from channels import SupportsRecv, SupportsSend
from ircv3 import IRCv3CommandProtocol


class Pipe(Protocol):

    @abstractmethod
    def __call__(
        self,
        istream: SupportsRecv[IRCv3CommandProtocol],
        ostream: SupportsSend[IRCv3CommandProtocol | str],
        /,
    ) -> Coroutine:
        raise NotImplementedError
