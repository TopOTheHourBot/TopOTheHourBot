from __future__ import annotations

__all__ = ["Client", "ClientWriter"]

from collections import defaultdict
from collections.abc import Set
from typing import (Final, Never, Protocol, Self, cast, override,
                    runtime_checkable)

import websockets
from ircv3.common import Ping, Welcome
from ircv3.twitch import (ClientJoin, ClientMessage, ClientPart, ServerJoin,
                          ServerMessage, ServerPart, UserState)
from websockets import ConnectionClosed

from .parser import ServerCommandParser
from .utilities import RateLimiter, Signal


class WebSocketLike(Protocol):
    @property
    def latency(self) -> float: ...
    async def send(self, data: str, /) -> object: ...
    async def close(self) -> object: ...


class WebSocketDummy(WebSocketLike):

    __slots__ = ()

    # XXX: Log these method calls?
    # It's VERY tempting to name this class "WebMocket"

    @property
    @override
    def latency(self) -> Never:
        raise NotImplementedError("WebSocket is disconnected")

    @override
    async def send(self, data: str, /) -> Never:
        raise NotImplementedError("WebSocket is disconnected")

    @override
    async def close(self) -> Never:
        raise NotImplementedError("WebSocket is disconnected")


# TODO: Use singleton instance?


@runtime_checkable
class SupportsOnClientWelcome(Protocol):
    async def on_client_welcome(self, writer: ClientWriter, command: Welcome, /) -> object: ...

@runtime_checkable
class SupportsOnClientPing(Protocol):
    async def on_client_ping(self, writer: ClientWriter, command: Ping, /) -> object: ...

@runtime_checkable
class SupportsOnClientMessage(Protocol):
    async def on_client_message(self, writer: ClientWriter, command: ServerMessage, /) -> object: ...

@runtime_checkable
class SupportsOnClientJoin(Protocol):
    async def on_client_join(self, writer: ClientWriter, command: ServerJoin, /) -> object: ...

@runtime_checkable
class SupportsOnClientPart(Protocol):
    async def on_client_part(self, writer: ClientWriter, command: ServerPart, /) -> object: ...

type SupportsOnClientCommand = (
    SupportsOnClientWelcome
    | SupportsOnClientPing
    | SupportsOnClientMessage
    | SupportsOnClientJoin
    | SupportsOnClientPart  # TODO: Add SupportsOnClientUserState
)


class Client:

    uri: Final[str] = "ws://irc-ws.chat.twitch.tv:80"

    __slots__ = (
        "oauth_token",
        "name",
        "room",
        "welcome_signal",
        "ping_signal",
        "message_signal",
        "join_signal",
        "part_signal",
        "user_state_signal",
        "_moderated_rooms",
    )
    oauth_token: str
    name: str
    room: str
    welcome_signal: Signal[[ClientWriter, Welcome], object]
    ping_signal: Signal[[ClientWriter, Ping], object]
    message_signal: Signal[[ClientWriter, ServerMessage], object]
    join_signal: Signal[[ClientWriter, ServerJoin], object]
    part_signal: Signal[[ClientWriter, ServerPart], object]
    user_state_signal: Signal[[ClientWriter, UserState], object]
    _moderated_rooms: set[str]

    def __init__(self, *, oauth_token: str, name: str) -> None:
        self.oauth_token = oauth_token
        self.name = name
        self.room = "#" + name
        self.welcome_signal = Signal()
        self.ping_signal = Signal().add_callback(self._on_ping)
        self.message_signal = Signal()
        self.join_signal = Signal()
        self.part_signal = Signal()
        self.user_state_signal = Signal().add_callback(self._on_user_state)
        self._moderated_rooms = {self.room,}  # Client is always a moderator of their own room

    async def _on_ping(self, writer: ClientWriter, command: Ping) -> None:
        await writer.pong(command)

    async def _on_user_state(self, writer: ClientWriter, command: UserState) -> None:
        moderated_rooms = self._moderated_rooms
        room = command.room
        if not command.moderator:  # XXX: Is the moderator flag on if client == broadcaster?
            moderated_rooms.discard(room)
        else:
            moderated_rooms.add(room)

    @property
    def moderated_rooms(self) -> Set[str]:
        return self._moderated_rooms

    def add_callbacks(self, suite: SupportsOnClientCommand) -> Self:
        if isinstance(suite, SupportsOnClientWelcome):
            self.welcome_signal.add_callback(suite.on_client_welcome)
        if isinstance(suite, SupportsOnClientPing):
            self.ping_signal.add_callback(suite.on_client_ping)
        if isinstance(suite, SupportsOnClientMessage):
            self.message_signal.add_callback(suite.on_client_message)
        if isinstance(suite, SupportsOnClientJoin):
            self.join_signal.add_callback(suite.on_client_join)
        if isinstance(suite, SupportsOnClientPart):
            self.part_signal.add_callback(suite.on_client_part)
        return self

    def remove_callbacks(self, suite: SupportsOnClientCommand) -> Self:
        if isinstance(suite, SupportsOnClientWelcome):
            self.welcome_signal.remove_callback(suite.on_client_welcome)
        if isinstance(suite, SupportsOnClientPing):
            self.ping_signal.remove_callback(suite.on_client_ping)
        if isinstance(suite, SupportsOnClientMessage):
            self.message_signal.remove_callback(suite.on_client_message)
        if isinstance(suite, SupportsOnClientJoin):
            self.join_signal.remove_callback(suite.on_client_join)
        if isinstance(suite, SupportsOnClientPart):
            self.part_signal.remove_callback(suite.on_client_part)
        return self

    async def run(self) -> None:
        writer = ClientWriter(self)
        signal_map = {
            ServerMessage: self.message_signal,
            UserState: self.user_state_signal,
            Ping: self.ping_signal,
            ServerJoin: self.join_signal,
            ServerPart: self.part_signal,
            Welcome: self.welcome_signal,
        }
        async for websocket in websockets.connect(self.uri):
            try:  # TODO: Manual close() call should stop this loop
                await writer.authenticate()
                writer.websocket = websocket
                async for data in websocket:
                    data = cast(str, data)
                    for command in ServerCommandParser(data):
                        signal = signal_map.get(type(command))  # type: ignore
                        if signal is None:
                            continue
                        signal.maybe_run(writer, command)  # type: ignore
            except ConnectionClosed:
                pass
            finally:
                writer.websocket = WebSocketDummy()


class ClientWriter:

    _authenticate_limiters = defaultdict[str, RateLimiter](lambda: RateLimiter(20, time_off=10))
    _join_limiters = defaultdict[str, RateLimiter](lambda: RateLimiter(20, time_off=10))
    _global_message_limiters = defaultdict[str, RateLimiter](lambda: RateLimiter(20, time_off=30))
    _local_message_limiters = defaultdict[str, RateLimiter](lambda: RateLimiter(100, time_off=30))

    __slots__ = ("client", "websocket")
    client: Client
    websocket: WebSocketLike

    def __init__(self, client: Client) -> None:
        self.client = client
        self.websocket = WebSocketDummy()

    @property
    def oauth_token(self) -> str:
        return self.client.oauth_token

    @property
    def name(self) -> str:
        return self.client.name

    @property
    def room(self) -> str:
        return self.client.room

    @property
    def moderated_rooms(self) -> Set[str]:
        return self.client.moderated_rooms

    @property
    def latency(self) -> float:
        return self.websocket.latency * 1000

    @property
    def authenticate_limiter(self) -> RateLimiter:
        return ClientWriter._authenticate_limiters[self.name]

    @property
    def join_limiter(self) -> RateLimiter:
        return ClientWriter._join_limiters[self.name]

    @property
    def global_message_limiter(self) -> RateLimiter:
        return ClientWriter._global_message_limiters[self.name]

    @property
    def local_message_limiter(self) -> RateLimiter:
        return ClientWriter._local_message_limiters[self.name]

    async def send(self, command: object) -> None:
        data = str(command)
        await self.websocket.send(data)

    async def authenticate(self) -> None:
        await self.authenticate_limiter
        await self.send("CAP REQ :twitch.tv/commands twitch.tv/membership twitch.tv/tags")
        await self.send(f"PASS oauth:{self.oauth_token}")
        await self.send(f"NICK {self.name}")

    async def pong(self, target: Ping) -> None:
        await self.send(target.reply())

    async def message(self, comment: object, target: ServerMessage | str) -> None:
        comment = str(comment)
        if isinstance(target, ServerMessage):
            command = target.reply(comment)
            room = target.room
        else:
            command = ClientMessage(target, comment)
            room = target
        t1_limiter = self.global_message_limiter
        if room in self.moderated_rooms:
            t1_limiter.admit()
            t2_limiter = self.local_message_limiter
            await t2_limiter
        else:
            await t1_limiter
        await self.send(command)

    async def join(self, *rooms: str) -> None:
        await self.join_limiter
        await self.send(ClientJoin(*rooms))

    async def part(self, *rooms: str) -> None:
        await self.send(ClientPart(*rooms))

    async def close(self) -> None:
        await self.websocket.close()
