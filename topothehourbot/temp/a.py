from __future__ import annotations

from abc import ABCMeta, abstractmethod
from asyncio import TaskGroup
from collections import deque
from collections.abc import AsyncIterator, Coroutine, Iterable, Iterator
from typing import Any, Self, override

from ircv3 import (IRCv3ClientCommandProtocol, IRCv3Command,
                   IRCv3ServerCommandProtocol)
from ircv3.dialects.twitch import (ClientJoin, Ping, RoomState, ServerJoin,
                                   ServerPart, ServerPrivateMessage)
from websockets import ConnectionClosed, Data, WebSocketClientProtocol

from series import series


class TwitchCallbackProtocol(metaclass=ABCMeta):

    __slots__ = ()

    @series
    async def on_connect(self) -> AsyncIterator[IRCv3ClientCommandProtocol]:
        """Event handler called when the client first connects to the Twitch
        IRC server
        """
        return
        yield

    @series
    async def on_join(self, join: ServerJoin) -> AsyncIterator[IRCv3ClientCommandProtocol]:
        """Event handler called when the client receives a JOIN from the Twitch
        IRC server
        """
        return
        yield

    @series
    async def on_part(self, part: ServerPart) -> AsyncIterator[IRCv3ClientCommandProtocol]:
        """Event handler called when the client receives a PART from the Twitch
        IRC server
        """
        return
        yield

    @series
    async def on_message(self, message: ServerPrivateMessage) -> AsyncIterator[IRCv3ClientCommandProtocol]:
        """Event handler called when the client receives a PRIVMSG from the
        Twitch IRC server
        """
        return
        yield

    @series
    async def on_room_state(self, room_state: RoomState) -> AsyncIterator[IRCv3ClientCommandProtocol]:
        """Event handler called when the client receives a ROOMSTATE from the
        Twitch IRC server
        """
        return
        yield


class TwitchCallbackBroadcaster(TwitchCallbackProtocol, metaclass=ABCMeta):

    __slots__ = ("_listeners")
    _listeners: set[TwitchCallbackProtocol]

    def __init__(self, *, listeners: Iterable[TwitchCallbackProtocol] = ()) -> None:
        self._listeners = set(listeners)

    def listeners(self) -> Iterator[TwitchCallbackProtocol]:
        """Return an iterator over the currently-enrolled listeners"""
        return iter(self._listeners)

    def enroll_listener(self, listener: TwitchCallbackProtocol, /) -> Self:
        """Enroll a listener and return the broadcaster

        The listener object must be hashable.
        """
        self._listeners.add(listener)
        return self

    def unenroll_listener(self, listener: TwitchCallbackProtocol, /) -> Self:
        """Unenroll a listener and return the broadcaster"""
        self._listeners.discard(listener)
        return self

    @abstractmethod
    async def event_callback(self, command: IRCv3ClientCommandProtocol) -> None:
        """Return a callback function used when a listener's event handler
        emits a client command in response
        """
        raise NotImplementedError

    @override
    @series
    async def on_connect(self) -> AsyncIterator[IRCv3ClientCommandProtocol]:
        listeners = self.listeners()
        listener = next(listeners, None)
        if listener is None:
            return
        async with TaskGroup() as tasks:
            calls = (listener.on_connect() for listener in listeners)
            async for command in (
                listener.on_connect()
                        .merge(*calls)
            ):
                tasks.create_task(self.event_callback(command))
        return
        yield

    @override
    @series
    async def on_join(self, join: ServerJoin) -> AsyncIterator[IRCv3ClientCommandProtocol]:
        listeners = self.listeners()
        listener = next(listeners, None)
        if listener is None:
            return
        async with TaskGroup() as tasks:
            calls = (listener.on_join(join) for listener in listeners)
            async for command in (
                listener.on_join(join)
                        .merge(*calls)
            ):
                tasks.create_task(self.event_callback(command))
        return
        yield

    @override
    @series
    async def on_part(self, part: ServerPart) -> AsyncIterator[IRCv3ClientCommandProtocol]:
        listeners = self.listeners()
        listener = next(listeners, None)
        if listener is None:
            return
        async with TaskGroup() as tasks:
            calls = (listener.on_part(part) for listener in listeners)
            async for command in (
                listener.on_part(part)
                        .merge(*calls)
            ):
                tasks.create_task(self.event_callback(command))
        return
        yield

    @override
    @series
    async def on_message(self, message: ServerPrivateMessage) -> AsyncIterator[IRCv3ClientCommandProtocol]:
        listeners = self.listeners()
        listener = next(listeners, None)
        if listener is None:
            return
        async with TaskGroup() as tasks:
            calls = (listener.on_message(message) for listener in listeners)
            async for command in (
                listener.on_message(message)
                        .merge(*calls)
            ):
                tasks.create_task(self.event_callback(command))
        return
        yield

    @override
    @series
    async def on_room_state(self, room_state: RoomState) -> AsyncIterator[IRCv3ClientCommandProtocol]:
        listeners = self.listeners()
        listener = next(listeners, None)
        if listener is None:
            return
        async with TaskGroup() as tasks:
            calls = (listener.on_room_state(room_state) for listener in listeners)
            async for command in (
                listener.on_room_state(room_state)
                        .merge(*calls)
            ):
                tasks.create_task(self.event_callback(command))
        return
        yield


class TwitchClient(TwitchCallbackBroadcaster):

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
        listeners: Iterable[TwitchCallbackProtocol] = (),
    ) -> None:
        super().__init__(listeners=listeners)
        self._client = client
        self._user = user
        self._token = token

    @property
    def user(self) -> str:
        return self._user

    def _parse_commands(self, data: Data) -> Iterator[IRCv3ServerCommandProtocol]:
        crlf = "\r\n"
        if isinstance(data, bytes):
            data = data.decode()
        assert isinstance(data, str)
        for command in map(
            IRCv3Command.from_string,
            data.rstrip(crlf).split(crlf)
        ):
            name = command.name
            if name == "PRIVMSG":
                type = ServerPrivateMessage
            elif name == "ROOMSTATE":
                type = RoomState
            elif name == "PING":
                type = Ping
            elif name == "JOIN":
                type = ServerJoin
            elif name == "PART":
                type = ServerPart
            else:
                continue
            yield type.cast(command)

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
        commands = self._parse_commands(await self._client.recv())
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

    @series
    async def on_ping(self, ping: Ping) -> AsyncIterator[IRCv3ClientCommandProtocol]:
        """Event handler called when the client receives a PING from the Twitch
        IRC server
        """
        yield ping.reply()


class TwitchRoom(TwitchCallbackBroadcaster):

    __slots__ = ("_client", "_room")
    _client: TwitchClient
    _room: str

    def __init__(
        self,
        client: TwitchClient,
        *,
        room: str,
        listeners: Iterable[TwitchCallbackProtocol] = (),
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
    @series
    async def on_connect(self) -> AsyncIterator[IRCv3ClientCommandProtocol]:
        yield ClientJoin(self.room)
        async for command in super().on_connect():
            yield command

    @override
    @series
    async def on_join(self, join: ServerJoin) -> AsyncIterator[IRCv3ClientCommandProtocol]:
        if self.room != join.room:
            return
        async for command in super().on_join(join):
            yield command

    @override
    @series
    async def on_part(self, part: ServerPart) -> AsyncIterator[IRCv3ClientCommandProtocol]:
        if self.room != part.room:
            return
        async for command in super().on_part(part):
            yield command

    @override
    @series
    async def on_message(self, message: ServerPrivateMessage) -> AsyncIterator[IRCv3ClientCommandProtocol]:
        if self.room != message.room:
            return
        async for command in super().on_message(message):
            yield command

    @override
    @series
    async def on_room_state(self, room_state: RoomState) -> AsyncIterator[IRCv3ClientCommandProtocol]:
        if self.room != room_state.room:
            return
        async for command in super().on_room_state(room_state):
            yield command
