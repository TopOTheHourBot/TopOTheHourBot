from __future__ import annotations

__all__ = ["Room"]

from collections.abc import AsyncIterator, Coroutine, Iterable
from typing import Any, override

from ircv3 import IRCv3ClientCommandProtocol
from ircv3.dialects.twitch import (ClientJoin, RoomState, ServerJoin,
                                   ServerPart, ServerPrivateMessage)

from .abc import EventListener, EventRebroadcaster
from .client import Client
from .series import Series


class Room(EventRebroadcaster):

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
    @Series.from_generator
    async def on_connect(self) -> AsyncIterator[IRCv3ClientCommandProtocol]:
        yield ClientJoin(self.room)
        async for feedback in super().on_connect():
            yield feedback

    @override
    @Series.from_generator
    async def on_join(self, command: ServerJoin, /) -> AsyncIterator[IRCv3ClientCommandProtocol]:
        if self.room != command.room:
            return
        async for feedback in super().on_join(command):
            yield feedback

    @override
    @Series.from_generator
    async def on_part(self, command: ServerPart, /) -> AsyncIterator[IRCv3ClientCommandProtocol]:
        if self.room != command.room:
            return
        async for feedback in super().on_part(command):
            yield feedback

    @override
    @Series.from_generator
    async def on_message(self, command: ServerPrivateMessage, /) -> AsyncIterator[IRCv3ClientCommandProtocol]:
        if self.room != command.room:
            return
        async for feedback in super().on_message(command):
            yield feedback

    @override
    @Series.from_generator
    async def on_room_state(self, command: RoomState, /) -> AsyncIterator[IRCv3ClientCommandProtocol]:
        if self.room != command.room:
            return
        async for feedback in super().on_room_state(command):
            yield feedback
