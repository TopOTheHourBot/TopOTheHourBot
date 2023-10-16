from __future__ import annotations

__all__ = ["TwitchChannel"]

from collections.abc import Iterator
from typing import Final, Literal, override

from channels import Signal, SupportsRecv
from ircv3 import IRCv3Command, IRCv3CommandProtocol
from ircv3.dialects.twitch import Ping, ServerPrivmsg
from websockets.client import WebSocketClientProtocol
from websockets.exceptions import ConnectionClosed

from .protocols import IRCv3Stream

CRLF: Final[Literal["\r\n"]] = "\r\n"


class TwitchChannel(IRCv3Stream, SupportsRecv[Iterator[IRCv3CommandProtocol]]):

    __slots__ = ("_connection")
    _connection: WebSocketClientProtocol

    def __init__(self, connection: WebSocketClientProtocol, /) -> None:
        self._connection = connection

    @property
    @override
    def latency(self) -> float:
        return self._connection.latency

    @override
    async def send(self, command: IRCv3CommandProtocol | str) -> None:
        data = str(command)
        try:
            await self._connection.send(data)
        except ConnectionClosed:
            return

    @override
    async def recv(self) -> Iterator[IRCv3CommandProtocol] | Signal:
        try:
            data = await self._connection.recv()
        except ConnectionClosed:
            return Signal.STOP
        assert isinstance(data, str)
        return self._command_iterator(data)

    def _command_iterator(self, data: str) -> Iterator[IRCv3CommandProtocol]:
        for command in map(
            IRCv3Command.from_string,
            data.rstrip(CRLF).split(CRLF),
        ):
            name = command.name
            if name == "PRIVMSG":
                yield ServerPrivmsg.cast(command)
            elif name == "PING":
                yield Ping.cast(command)
            else:
                yield command
