from __future__ import annotations

__all__ = [
    "ISStream",
    "OMStream",
    "OSStream",
    "IOSStream",
    "Pipe",
    "Transport",
]

from abc import abstractmethod
from collections.abc import Coroutine
from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar, TypeAlias

from channels import SupportsRecv, SupportsSend, SupportsSendAndRecv
from ircv3 import IRCv3CommandProtocol
from ircv3.dialects.twitch import ClientPrivmsg

ClientPrivmsgT = TypeVar("ClientPrivmsgT", covariant=True, bound=ClientPrivmsg | str)
ClientCommandT = TypeVar("ClientCommandT", covariant=True, bound=IRCv3CommandProtocol | str)
ServerCommandT = TypeVar("ServerCommandT", contravariant=True, bound=IRCv3CommandProtocol)

ISStream: TypeAlias = SupportsRecv[ServerCommandT]  # Input System Stream
OMStream: TypeAlias = SupportsSend[ClientPrivmsgT]  # Output Message Stream
OSStream: TypeAlias = SupportsSend[ClientCommandT]  # Output System Stream

IOSStream: TypeAlias = SupportsSendAndRecv[ServerCommandT, ServerCommandT]  # Input/Output System Stream


class Pipe(Protocol[ServerCommandT, ClientPrivmsgT, ClientCommandT]):

    @abstractmethod
    def __call__(
        self,
        isstream: ISStream[ServerCommandT],
        omstream: OMStream[ClientPrivmsgT],
        osstream: OSStream[ClientCommandT],
        /,
    ) -> Coroutine:
        raise NotImplementedError


@dataclass(slots=True, repr=False, match_args=False)
class Transport(SupportsSend[ServerCommandT], Generic[ServerCommandT, ClientPrivmsgT, ClientCommandT]):

    pipe: Pipe[ServerCommandT, ClientPrivmsgT, ClientCommandT]
    iosstream: IOSStream[ServerCommandT]
    omstream: OMStream[ClientPrivmsgT]
    osstream: OSStream[ClientCommandT]

    def send(self, command: ServerCommandT) -> Coroutine:
        return self.iosstream.send(command)

    def open(self) -> Coroutine:
        return self.pipe(self.iosstream, self.omstream, self.osstream)
