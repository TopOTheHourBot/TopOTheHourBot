from __future__ import annotations

__all__ = [
    "ServerCommand",
    "ClientMessage",
    "ClientCommand",
    "ISStream",
    "OMStream",
    "OSStream",
    "IOSStream",
    "DBStream",
    "Pipe",
    "Transport",
]

from abc import abstractmethod
from collections.abc import Coroutine
from dataclasses import dataclass
from typing import Any, Protocol, override

from channels import SupportsRecv, SupportsSend, SupportsSendAndRecv
from ircv3 import IRCv3CommandProtocol
from ircv3.dialects.twitch import ClientPrivmsg

from .channels import SQLiteChannel

type ServerCommand = IRCv3CommandProtocol
type ClientMessage = ClientPrivmsg | str
type ClientCommand = IRCv3CommandProtocol | str

type ISStream[ServerCommandT: ServerCommand] = SupportsRecv[ServerCommandT]
type OMStream[ClientMessageT: ClientMessage] = SupportsSend[ClientMessageT]
type OSStream[ClientCommandT: ClientCommand] = SupportsSend[ClientCommandT]

type IOSStream[ServerCommandT: ServerCommand] = SupportsSendAndRecv[ServerCommandT, ServerCommandT]

type DBStream = SQLiteChannel  # May be broader in the future?


class Pipe[
    ServerCommandT: ServerCommand,
    ClientMessageT: ClientMessage,
    ClientCommandT: ClientCommand,
](Protocol):

    @abstractmethod
    def __call__(
        self,
        isstream: ISStream[ServerCommandT],
        omstream: OMStream[ClientMessageT],
        osstream: OSStream[ClientCommandT],
        dbstream: DBStream,
        /,
    ) -> Coroutine[Any, Any, object]:
        raise NotImplementedError


@dataclass(slots=True, repr=False, match_args=False)
class Transport[
    ServerCommandT: ServerCommand,
    ClientMessageT: ClientMessage,
    ClientCommandT: ClientCommand,
](SupportsSend[ServerCommandT]):

    pipe: Pipe[ServerCommandT, ClientMessageT, ClientCommandT]
    iosstream: IOSStream[ServerCommandT]
    omstream: OMStream[ClientMessageT]
    osstream: OSStream[ClientCommandT]
    dbstream: DBStream

    @override
    def send(self, command: ServerCommandT) -> Coroutine[Any, Any, object]:
        return self.iosstream.send(command)

    def open(self) -> Coroutine[Any, Any, object]:
        return self.pipe(self.iosstream, self.omstream, self.osstream, self.dbstream)
