from __future__ import annotations

__all__ = [
    "PluginLoader",
    "Plugin",
    "ClientApp",
    "ChannelApp",
]

from typing import Protocol, Self, override

import websockets
from ircv3 import Ping
from ircv3.dialects.twitch import ServerJoin, ServerMessage, ServerPart

from .client import Channel, Client
from .parser import ServerCommandParser
from .utilities import Signal


class PluginLoader(Protocol):

    def load(self, plugin: Plugin[Self]) -> Self:
        return plugin.on_load(self)

    def unload(self, plugin: Plugin[Self]) -> Self:
        return plugin.on_unload(self)


class Plugin[LoaderT](Protocol):

    def on_load(self, loader: LoaderT, /) -> LoaderT:
        return loader

    def on_unload(self, loader: LoaderT, /) -> LoaderT:
        return loader


class ClientApp(PluginLoader):

    uri: str = "ws://irc-ws.chat.twitch.tv:80"

    __slots__ = (
        "oauth_token",
        "name",
        "ready_signal",
        "ping_signal",
        "message_signal",
        "join_signal",
        "part_signal",
    )
    oauth_token: str
    name: str
    ready_signal: Signal[[Client], object]
    ping_signal: Signal[[Client, Ping], object]
    message_signal: Signal[[Client, ServerMessage], object]
    join_signal: Signal[[Client, ServerJoin], object]
    part_signal: Signal[[Client, ServerPart], object]

    def __init__(self, *, oauth_token: str, name: str) -> None:
        self.oauth_token = oauth_token
        self.name = name
        self.ready_signal = Signal()
        self.ping_signal = Signal().add_callback(self._on_client_ping)
        self.message_signal = Signal()
        self.join_signal = Signal()
        self.part_signal = Signal()

    async def _on_client_ping(self, client: Client, ping: Ping) -> None:
        await client.send(ping.reply())

    async def run(self) -> None:
        async for websocket in websockets.connect(self.uri):
            client = Client(websocket, name=self.name)
            await client.send("CAP REQ :twitch.tv/commands twitch.tv/membership twitch.tv/tags")
            await client.send(f"PASS oauth:{self.oauth_token}")
            await client.send(f"NICK {self.name}")
            waiter = self.ready_signal.maybe_run(client)
            if waiter is not None:
                await waiter
            async for data in websocket:
                assert isinstance(data, str)
                parser = ServerCommandParser(data)
                for command in parser:
                    if isinstance(command, ServerMessage):
                        self.message_signal.maybe_run(client, command)
                    elif isinstance(command, Ping):
                        self.ping_signal.run(client, command)  # We always provide one callback
                    elif isinstance(command, ServerJoin):
                        self.join_signal.maybe_run(client, command)
                    elif isinstance(command, ServerPart):
                        self.part_signal.maybe_run(client, command)


class ChannelApp(PluginLoader, Plugin[ClientApp]):

    __slots__ = (
        "name",
        "room",
        "ready_signal",
        "message_signal",
        "join_signal",
        "part_signal",
    )
    name: str
    room: str
    ready_signal: Signal[[Channel], object]
    message_signal: Signal[[Channel, ServerMessage], object]
    join_signal: Signal[[Channel, ServerJoin], object]
    part_signal: Signal[[Channel, ServerPart], object]

    def __init__(self, name: str) -> None:
        self.name = name
        self.room = "#" + name
        self.ready_signal = Signal()
        self.message_signal = Signal()
        self.join_signal = Signal()
        self.part_signal = Signal()

    async def _on_client_ready(self, client: Client) -> None:
        await client.join(self.room)
        waiter = self.ready_signal.maybe_run(client.channel(self.name))
        if waiter is not None:
            await waiter

    async def _on_client_message(self, client: Client, message: ServerMessage) -> None:
        if self.room != message.room:
            return
        self.message_signal.maybe_run(
            client.channel(self.name),
            message,
        )

    async def _on_client_join(self, client: Client, join: ServerJoin) -> None:
        if self.room != join.room:
            return
        self.join_signal.maybe_run(
            client.channel(self.name),
            join,
        )

    async def _on_client_part(self, client: Client, part: ServerPart) -> None:
        if self.room != part.room:
            return
        self.part_signal.maybe_run(
            client.channel(self.name),
            part,
        )

    @override
    def on_load(self, app: ClientApp) -> ClientApp:
        app = super().on_load(app)
        app.ready_signal.add_callback(self._on_client_ready)
        app.message_signal.add_callback(self._on_client_message)
        app.join_signal.add_callback(self._on_client_join)
        app.part_signal.add_callback(self._on_client_part)
        return app

    @override
    def on_unload(self, app: ClientApp) -> ClientApp:
        app = super().on_unload(app)
        app.ready_signal.remove_callback(self._on_client_ready)
        app.message_signal.remove_callback(self._on_client_message)
        app.join_signal.remove_callback(self._on_client_join)
        app.part_signal.remove_callback(self._on_client_part)
        return app
