from __future__ import annotations

__all__ = [
    "Pipe",
    "Transport",
]

from abc import abstractmethod
from collections.abc import Coroutine
from dataclasses import dataclass
from typing import Protocol

from ircv3 import IRCv3CommandProtocol
from channels import SupportsRecv, SupportsSend, SupportsSendAndRecv


class Pipe(Protocol):

    @abstractmethod
    def __call__(
        self,
        isstream: SupportsRecv[IRCv3CommandProtocol],
        omstream: SupportsSend[IRCv3CommandProtocol | str],
        osstream: SupportsSend[IRCv3CommandProtocol | str],
        /,
    ) -> Coroutine:
        raise NotImplementedError


@dataclass(slots=True, eq=False, repr=False, match_args=False)
class Transport:

    pipe: Pipe
    iosstream: SupportsSendAndRecv[IRCv3CommandProtocol, IRCv3CommandProtocol]
    omstream: SupportsSend[IRCv3CommandProtocol | str]
    osstream: SupportsSend[IRCv3CommandProtocol | str]

    def send(self, command: IRCv3CommandProtocol) -> Coroutine:
        """Send a command to ``iosstream``"""
        return self.iosstream.send(command)

    def open(self) -> Coroutine:
        return self.pipe(self.iosstream, self.omstream, self.osstream)
