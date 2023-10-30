from __future__ import annotations

__all__ = ["Client"]

from collections import deque
from collections.abc import AsyncIterator, Coroutine, Iterable, Iterator
from typing import Any, Final, Literal, override

from ircv3 import (IRCv3ClientCommandProtocol, IRCv3Command,
                   IRCv3ServerCommandProtocol)
from ircv3.dialects.twitch import (Ping, RoomState, ServerJoin, ServerPart,
                                   ServerPrivateMessage)
from websockets import ConnectionClosed, Data, WebSocketClientProtocol

from .abc import EventBroadcaster, EventListener
from .series import series

CRLF: Final[Literal["\r\n"]] = "\r\n"


def parse_commands(data: Data) -> Iterator[IRCv3ServerCommandProtocol]:
    if isinstance(data, bytes):
        data = data.decode()
    assert isinstance(data, str)
    for command in map(
        IRCv3Command.from_string,
        data.rstrip(CRLF).split(CRLF)
    ):
        name = command.name
        if name == "PRIVMSG":
            yield ServerPrivateMessage.cast(command)
        elif name == "ROOMSTATE":
            yield RoomState.cast(command)
        elif name == "PING":
            yield Ping.cast(command)
        elif name == "JOIN":
            yield ServerJoin.cast(command)
        elif name == "PART":
            yield ServerPart.cast(command)


class Client(EventBroadcaster):

    __slots__ = ("_client", "_user", "_token")
    _client: WebSocketClientProtocol
    _user: str
    _token: str

    def __init__(
        self,
        client: WebSocketClientProtocol,
        *,
        user: str,
        token: str,
        listeners: Iterable[EventListener] = (),
    ) -> None:
        super().__init__(listeners=listeners)
        self._client = client
        self._user = user
        self._token = token

    @property
    def user(self) -> str:
        return self._user

    async def send(self, command: IRCv3ClientCommandProtocol) -> None:
        """Send a command to the Twitch IRC server"""
        data = str(command)
        try:
            await self._client.send(data)
        except ConnectionClosed:
            return  # Let recv() propagate

    async def recv(self, *, memo: deque[IRCv3ServerCommandProtocol] = deque()) -> IRCv3ServerCommandProtocol:
        """Receive a command from the Twitch IRC server

        Raises ``RuntimeError`` if called from two coroutines concurrently, or
        ``websockets.ConnectionClosed`` if the underlying connection was
        closed.
        """
        if memo:
            return memo.popleft()
        commands = parse_commands(await self._client.recv())
        command = next(commands)
        memo.extend(commands)
        return command

    @series
    async def recv_all(self) -> AsyncIterator[IRCv3ServerCommandProtocol]:
        """Return an asynchronous iterator that continuously receives commands
        from the Twitch IRC server until the connection has closed
        """
        try:
            while True:
                yield await self.recv()
        except ConnectionClosed:
            return

    @override
    def event_callback(self, command: IRCv3ClientCommandProtocol) -> Coroutine[Any, Any, None]:
        return self.send(command)
