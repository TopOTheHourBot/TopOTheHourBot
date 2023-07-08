from __future__ import annotations

__all__ = [
    "IRCv3Data",
    "IRCv3Channel",
]

from typing import TypeAlias

from websockets.client import WebSocketClientProtocol
from websockets.exceptions import ConnectionClosed

from .channeling import RecvError, SendError, SupportsRecvAndSend
from .commands import IRCv3Command

IRCv3Data: TypeAlias = IRCv3Command | str


class IRCv3Channel(SupportsRecvAndSend[IRCv3Command, IRCv3Data]):

    __slots__ = ("_socket")
    _socket: WebSocketClientProtocol

    def __init__(self, socket: WebSocketClientProtocol, /) -> None:
        self._socket = socket

    async def recv(self) -> IRCv3Command:
        try:
            string = await self._socket.recv()
        except ConnectionClosed as exc:
            raise RecvError from exc
        assert isinstance(string, str)
        return IRCv3Command.from_string(string)

    async def send(self, value: IRCv3Data, /) -> None:
        string = str(value)
        try:
            await self._socket.send(string)
        except ConnectionClosed as exc:
            raise SendError from exc
