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
from typing import Any, Protocol, override

from channels import SupportsRecv, SupportsSend, SupportsSendAndRecv
from ircv3 import IRCv3CommandProtocol
from ircv3.dialects.twitch import ClientPrivmsg

type ISStream[ServerCommandT: IRCv3CommandProtocol] = SupportsRecv[ServerCommandT]
type OMStream[ClientPrivmsgT: ClientPrivmsg | str] = SupportsSend[ClientPrivmsgT]
type OSStream[ClientCommandT: IRCv3CommandProtocol | str] = SupportsSend[ClientCommandT]

type IOSStream[ServerCommandT: IRCv3CommandProtocol] = SupportsSendAndRecv[ServerCommandT, ServerCommandT]


class Pipe[
    ServerCommandT: IRCv3CommandProtocol,
    ClientPrivmsgT: ClientPrivmsg | str,
    ClientCommandT: IRCv3CommandProtocol | str,
](Protocol):

    @abstractmethod
    def __call__(
        self,
        isstream: ISStream[ServerCommandT],
        omstream: OMStream[ClientPrivmsgT],
        osstream: OSStream[ClientCommandT],
        /,
    ) -> Coroutine[Any, Any, object]:
        raise NotImplementedError


@dataclass(slots=True, repr=False, match_args=False)
class Transport[
    ServerCommandT: IRCv3CommandProtocol,
    ClientPrivmsgT: ClientPrivmsg | str,
    ClientCommandT: IRCv3CommandProtocol | str,
](SupportsSend[ServerCommandT]):

    pipe: Pipe[ServerCommandT, ClientPrivmsgT, ClientCommandT]
    iosstream: IOSStream[ServerCommandT]
    omstream: OMStream[ClientPrivmsgT]
    osstream: OSStream[ClientCommandT]

    @override
    def send(self, command: ServerCommandT) -> Coroutine[Any, Any, object]:
        return self.iosstream.send(command)

    def open(self) -> Coroutine[Any, Any, object]:
        return self.pipe(self.iosstream, self.omstream, self.osstream)
