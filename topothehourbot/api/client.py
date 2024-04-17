from __future__ import annotations

__all__ = ["ClientApp", "Client"]

from collections import defaultdict
from collections.abc import Coroutine, Set
from typing import Any, Protocol, Self, override, runtime_checkable

from ircv3.common import Ping, Welcome
from ircv3.twitch import (ClientJoin, ClientMessage, ClientPart,
                          GlobalUserState, ServerJoin, ServerMessage,
                          ServerPart, UserState)

from .parser import ServerCommandParser
from .utilities import RateLimiter, Signal
from .websocket import (SupportsOnWebSocketConnect, SupportsOnWebSocketText,
                        WebSocket, WebSocketApp)


@runtime_checkable
class SupportsOnClientWelcome(Protocol):
    def on_client_welcome(self, client: Client, command: Welcome, /) -> Coroutine[Any, Any, None] | None: ...

@runtime_checkable
class SupportsOnClientPing(Protocol):
    def on_client_ping(self, client: Client, command: Ping, /) -> Coroutine[Any, Any, None] | None: ...

@runtime_checkable
class SupportsOnClientMessage(Protocol):
    def on_client_message(self, client: Client, command: ServerMessage, /) -> Coroutine[Any, Any, None] | None: ...

@runtime_checkable
class SupportsOnClientJoin(Protocol):
    def on_client_join(self, client: Client, command: ServerJoin, /) -> Coroutine[Any, Any, None] | None: ...

@runtime_checkable
class SupportsOnClientPart(Protocol):
    def on_client_part(self, client: Client, command: ServerPart, /) -> Coroutine[Any, Any, None] | None: ...

@runtime_checkable
class SupportsOnClientUserState(Protocol):
    def on_client_user_state(self, client: Client, command: UserState, /) -> Coroutine[Any, Any, None] | None: ...

@runtime_checkable
class SupportsOnClientGlobalUserState(Protocol):
    def on_client_global_user_state(self, client: Client, command: GlobalUserState, /) -> Coroutine[Any, Any, None] | None: ...

type SupportsClientCallback = (
    SupportsOnClientWelcome
    | SupportsOnClientPing
    | SupportsOnClientMessage
    | SupportsOnClientJoin
    | SupportsOnClientPart
    | SupportsOnClientUserState
    | SupportsOnClientGlobalUserState
)


class ClientApp(
    SupportsOnWebSocketConnect,
    SupportsOnWebSocketText,
    SupportsOnClientPing,
    SupportsOnClientUserState,
):

    __slots__ = (
        "_app",
        "_moderated_rooms",
        "oauth_token",
        "name",
        "connect_signal",
        "welcome_signal",
        "ping_signal",
        "message_signal",
        "join_signal",
        "part_signal",
        "user_state_signal",
        "global_user_state_signal",
    )
    _app: WebSocketApp
    _moderated_rooms: set[str]
    oauth_token: str
    name: str
    connect_signal: Signal[[Client]]
    welcome_signal: Signal[[Client, Welcome]]
    ping_signal: Signal[[Client, Ping]]
    message_signal: Signal[[Client, ServerMessage]]
    join_signal: Signal[[Client, ServerJoin]]
    part_signal: Signal[[Client, ServerPart]]
    user_state_signal: Signal[[Client, UserState]]
    global_user_state_signal: Signal[[Client, GlobalUserState]]

    def __init__(self, *, oauth_token: str, name: str) -> None:
        self._app = WebSocketApp().add_callbacks(self)
        self._moderated_rooms = {"#" + name,}  # Client is always a moderator of their own room
        self.oauth_token = oauth_token
        self.name = name
        self.connect_signal = Signal()
        self.welcome_signal = Signal()
        self.ping_signal = Signal()
        self.message_signal = Signal()
        self.join_signal = Signal()
        self.part_signal = Signal()
        self.user_state_signal = Signal()
        self.global_user_state_signal = Signal()
        self.add_callbacks(self)

    @property
    def moderated_rooms(self) -> Set[str]:
        return self._moderated_rooms

    @override
    async def on_websocket_connect(self, websocket: WebSocket) -> None:
        client = Client(websocket, self)
        await client.authenticate()
        waiter = self.connect_signal.maybe_run(client)
        if waiter:
            await waiter

    @override
    async def on_websocket_text(self, websocket: WebSocket, text: str) -> None:
        for command in ServerCommandParser(text):
            client = Client(websocket, self)
            if isinstance(command, ServerMessage):
                self.message_signal.maybe_run(client, command)
            elif isinstance(command, UserState):
                self.user_state_signal.run(client, command)
            elif isinstance(command, GlobalUserState):
                self.global_user_state_signal.maybe_run(client, command)
            elif isinstance(command, Ping):
                self.ping_signal.run(client, command)
            elif isinstance(command, ServerJoin):
                self.join_signal.maybe_run(client, command)
            elif isinstance(command, ServerPart):
                self.part_signal.maybe_run(client, command)
            elif isinstance(command, Welcome):
                self.welcome_signal.maybe_run(client, command)

    @override
    async def on_client_ping(self, client: Client, command: Ping) -> None:
        await client.pong(command)

    @override
    async def on_client_user_state(self, client: Client, command: UserState) -> None:
        moderated_rooms = self._moderated_rooms
        room = command.room
        if not command.moderator:  # XXX: Is the moderator flag on if app == broadcaster?
            moderated_rooms.discard(room)
        else:
            moderated_rooms.add(room)

    def add_callbacks(self, suite: SupportsClientCallback) -> Self:
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
        if isinstance(suite, SupportsOnClientUserState):
            self.user_state_signal.add_callback(suite.on_client_user_state)
        if isinstance(suite, SupportsOnClientGlobalUserState):
            self.global_user_state_signal.add_callback(suite.on_client_global_user_state)
        return self

    def remove_callbacks(self, suite: SupportsClientCallback) -> Self:
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
        if isinstance(suite, SupportsOnClientUserState):
            self.user_state_signal.remove_callback(suite.on_client_user_state)
        if isinstance(suite, SupportsOnClientGlobalUserState):
            self.global_user_state_signal.remove_callback(suite.on_client_global_user_state)
        return self

    async def run(self) -> None:
        await self._app.run("ws://irc-ws.chat.twitch.tv:80")


class Client:

    _authenticate_limiters = defaultdict[str, RateLimiter](lambda: RateLimiter(20, time_off=10))
    _join_limiters = defaultdict[str, RateLimiter](lambda: RateLimiter(20, time_off=10))
    _global_message_limiters = defaultdict[str, RateLimiter](lambda: RateLimiter(20, time_off=30))
    _local_message_limiters = defaultdict[str, RateLimiter](lambda: RateLimiter(100, time_off=30))

    __slots__ = ("_websocket", "app")
    _websocket: WebSocket
    app: ClientApp

    def __init__(self, websocket: WebSocket, app: ClientApp) -> None:
        self._websocket = websocket
        self.app = app

    @property
    def _authenticate_limiter(self) -> RateLimiter:
        return Client._authenticate_limiters[self.name]

    @property
    def _join_limiter(self) -> RateLimiter:
        return Client._join_limiters[self.name]

    @property
    def _global_message_limiter(self) -> RateLimiter:
        return Client._global_message_limiters[self.name]

    @property
    def _local_message_limiter(self) -> RateLimiter:
        return Client._local_message_limiters[self.name]

    @property
    def latency(self) -> float:
        return self._websocket.latency

    @property
    def open(self) -> bool:
        return self._websocket.open

    @property
    def closed(self) -> bool:
        return self._websocket.closed

    @property
    def close_code(self) -> int | None:
        return self._websocket.close_code

    @property
    def close_reason(self) -> str | None:
        return self._websocket.close_reason

    @property
    def oauth_token(self) -> str:
        return self.app.oauth_token

    @property
    def name(self) -> str:
        return self.app.name

    @property
    def moderated_rooms(self) -> Set[str]:
        return self.app.moderated_rooms

    async def send(self, command: object) -> None:
        data = str(command)
        await self._websocket.send(data)

    async def authenticate(self) -> None:
        await self.send("CAP REQ :twitch.tv/commands twitch.tv/membership twitch.tv/tags")
        async with self._authenticate_limiter:
            await self.send(f"PASS oauth:{self.oauth_token}")
            await self.send(f"NICK {self.name}")

    async def pong(self, target: Ping) -> None:
        await self.send(target.reply())

    async def message(self, target: ServerMessage | str, comment: object) -> None:
        comment = str(comment)
        if isinstance(target, ServerMessage):
            command = target.reply(comment)
            room = target.room
        else:
            command = ClientMessage(target, comment)
            room = target
        limiter: RateLimiter
        global_limiter = self._global_message_limiter
        if room in self.moderated_rooms:
            global_limiter.increment()
            limiter = self._local_message_limiter
        else:
            limiter = global_limiter
        async with limiter:
            await self.send(command)

    async def join(self, *rooms: str) -> None:
        async with self._join_limiter:
            await self.send(ClientJoin(*rooms))

    async def part(self, *rooms: str) -> None:
        await self.send(ClientPart(*rooms))

    async def close(self) -> None:
        await self._websocket.close()
