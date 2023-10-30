from __future__ import annotations

__all__ = ["Room"]

from collections.abc import AsyncIterator, Coroutine, Iterable
from typing import Any, override

from ircv3 import IRCv3ClientCommandProtocol
from ircv3.dialects.twitch import (ClientJoin, RoomState, ServerJoin,
                                   ServerPart, ServerPrivateMessage)

from .abc import EventBroadcaster, EventListener
from .client import Client
from .series import series


class Room(EventBroadcaster):

    __slots__ = ("_client", "_room")
    _client: Client
    _room: str

    def __init__(
        self,
        client: Client,
        *,
        room: str,
        listeners: Iterable[EventListener] = (),
    ) -> None:
        super().__init__(listeners=listeners)
        self._client = client
        self._room = room

    @property
    def user(self) -> str:
        return self._client.user

    @property
    def room(self) -> str:
        return self._room

    @override
    def event_callback(self, command: IRCv3ClientCommandProtocol) -> Coroutine[Any, Any, None]:
        return self._client.event_callback(command)

    @override
    @series
    async def on_connect(self) -> AsyncIterator[IRCv3ClientCommandProtocol]:
        yield ClientJoin(self.room)
        await super().on_connect()

    @override
    async def on_join(self, join: ServerJoin) -> None:
        if self.room != join.room:
            return
        await super().on_join(join)

    @override
    async def on_part(self, part: ServerPart) -> None:
        if self.room != part.room:
            return
        await super().on_part(part)

    @override
    async def on_message(self, message: ServerPrivateMessage) -> None:
        if self.room != message.room:
            return
        await super().on_message(message)

    @override
    async def on_room_state(self, room_state: RoomState) -> None:
        if self.room != room_state.room:
            return
        await super().on_room_state(room_state)
