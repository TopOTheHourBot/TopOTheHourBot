from __future__ import annotations

__all__ = ["TwitchChannel"]

from collections.abc import Iterator
from typing import Final, Literal, override

from channels import StopRecv, StopSend, SupportsSendAndRecv
from ircv3 import IRCv3Command, IRCv3CommandProtocol
from ircv3.dialects.twitch import Ping, ServerPrivmsg
from websockets.client import WebSocketClientProtocol
from websockets.exceptions import ConnectionClosed


class TwitchChannel(SupportsSendAndRecv[IRCv3CommandProtocol | str, Iterator[IRCv3CommandProtocol]]):

    CRLF: Final[Literal["\r\n"]] = "\r\n"

    __slots__ = ("_socket")
    _socket: WebSocketClientProtocol

    def __init__(self, socket: WebSocketClientProtocol, /) -> None:
        self._socket = socket

    @override
    async def send(self, command: IRCv3CommandProtocol | str) -> None:
        data = str(command)
        try:
            await self._socket.send(data)
        except ConnectionClosed as error:
            raise StopSend from error

    @override
    async def recv(self) -> Iterator[IRCv3CommandProtocol]:
        try:
            data = await self._socket.recv()
        except ConnectionClosed as error:
            raise StopRecv from error
        assert isinstance(data, str)
        return self._command_iterator(data)

    def _command_iterator(self, data: str) -> Iterator[IRCv3CommandProtocol]:
        crlf = self.CRLF
        for command in map(
            IRCv3Command.from_string,
            data.rstrip(crlf).split(crlf),
        ):
            name = command.name
            if name == "PRIVMSG":
                yield ServerPrivmsg.cast(command)
            elif name == "PING":
                yield Ping.cast(command)
            else:
                yield command
