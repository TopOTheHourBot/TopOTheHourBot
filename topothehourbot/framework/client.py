from __future__ import annotations

__all__ = ["Client"]

import contextlib
from asyncio import TaskGroup
from collections.abc import AsyncIterator, Coroutine, Iterable, Iterator
from typing import Any, Final, Literal, Optional, cast, final, override

from ircv3 import IRCv3ClientCommandProtocol, IRCv3Command
from ircv3.dialects.twitch import (Ping, RoomState, ServerJoin, ServerPart,
                                   ServerPrivateMessage)
from websockets import ConnectionClosed, WebSocketClientProtocol

from .abc import EventBroadcaster, EventListener

CRLF: Final[Literal["\r\n"]] = "\r\n"


@final
class Client(EventBroadcaster):

    __slots__ = ("_client", "_user", "_auth_token")
    _client: WebSocketClientProtocol
    _user: str
    _auth_token: str

    def __init__(
        self,
        client: WebSocketClientProtocol,
        *,
        user: str,
        auth_token: str,
        listeners: Iterable[EventListener] = (),
    ) -> None:
        super().__init__(listeners=listeners)
        self._client = client
        self._user = user
        self._auth_token = auth_token

    @property
    def user(self) -> str:
        return self._user

    @override
    async def event_callback(self, command: IRCv3ClientCommandProtocol) -> None:
        data = str(command)
        with contextlib.suppress(ConnectionClosed):
            await self._client.send(data)

    def on_ping(self, ping: Ping) -> Coroutine[Any, Any, None]:
        return self.event_callback(ping.reply())

    def _parse_commands(self, data: str) -> Iterator[Coroutine[Any, Any, Optional[IRCv3ClientCommandProtocol]]]:
        raw_commands = data.rstrip(CRLF).split(CRLF)
        for command in map(IRCv3Command.from_string, raw_commands):
            name = command.name
            if name == "PRIVMSG":
                yield self.on_message(ServerPrivateMessage.cast(command))
            elif name == "ROOMSTATE":
                yield self.on_room_state(RoomState.cast(command))
            elif name == "PING":
                yield self.on_ping(Ping.cast(command))
            elif name == "JOIN":
                yield self.on_join(ServerJoin.cast(command))
            elif name == "PART":
                yield self.on_part(ServerPart.cast(command))

    async def _parse_data(self) -> AsyncIterator[Coroutine[Any, Any, Optional[IRCv3ClientCommandProtocol]]]:
        with contextlib.suppress(ConnectionClosed):
            while True:
                data = cast(str, await self._client.recv())
                for coro in self._parse_commands(data):
                    yield coro

    async def run(self) -> None:
        try:
            await self._client.send("CAP REQ :twitch.tv/commands twitch.tv/membership twitch.tv/tags")
            await self._client.send(f"PASS oauth:{self._auth_token}")
            await self._client.send(f"NICK {self._user}")
        except ConnectionClosed:
            return
        async with TaskGroup() as tasks:
            tasks.create_task(self.on_connect())
            async for coro in self._parse_data():
                tasks.create_task(coro)
