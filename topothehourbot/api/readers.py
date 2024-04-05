from __future__ import annotations

__all__ = ["ClientReader", "ChannelReader"]

from typing import Self

import websockets
from ircv3 import Ping, RPLWelcome
from ircv3.dialects.twitch import ServerJoin, ServerMessage, ServerPart

from .parser import ServerCommandParser
from .utilities import Signal
from .writers import ChannelWriter, ClientWriter


class ClientReader:

    uri: str = "ws://irc-ws.chat.twitch.tv:80"

    __slots__ = (
        "_channel_readers",
        "oauth_token",
        "name",
        "welcome_signal",
        "ping_signal",
        "message_signal",
        "join_signal",
        "part_signal",
    )
    _channel_readers: dict[str, ChannelReader]
    oauth_token: str
    name: str
    welcome_signal: Signal[[ClientWriter, RPLWelcome], object]
    ping_signal: Signal[[ClientWriter, Ping], object]
    message_signal: Signal[[ClientWriter, ServerMessage], object]
    join_signal: Signal[[ClientWriter, ServerJoin], object]
    part_signal: Signal[[ClientWriter, ServerPart], object]

    def __init__(self, *, oauth_token: str, name: str) -> None:
        self._channel_readers = {}
        self.oauth_token = oauth_token
        self.name = name
        self.welcome_signal = Signal()
        self.ping_signal = Signal().add_callback(self._on_client_ping)
        self.message_signal = Signal()
        self.join_signal = Signal()
        self.part_signal = Signal()

    async def _on_client_ping(self, client: ClientWriter, ping: Ping) -> None:
        await client.send(ping.reply())

    def create_channel_reader(self, name: str) -> ChannelReader:
        channel_reader: ChannelReader
        try:
            channel_reader = self._channel_readers[name]
        except KeyError:
            channel_reader = ChannelReader(self, name=name).add_callbacks()
            self._channel_readers[name] = channel_reader
        return channel_reader

    def destroy_channel_reader(self, name: str) -> ChannelReader | None:
        channel_reader = self._channel_readers.pop(name, None)
        if channel_reader is not None:
            channel_reader.remove_callbacks()
        return channel_reader

    async def read(self):
        async for websocket in websockets.connect(self.uri):
            writer = ClientWriter(websocket, name=self.name)
            await writer.send("CAP REQ :twitch.tv/commands twitch.tv/membership twitch.tv/tags")
            await writer.send(f"PASS oauth:{self.oauth_token}")
            await writer.send(f"NICK {self.name}")
            async for data in websocket:
                assert isinstance(data, str)
                parser = ServerCommandParser(data)
                for command in parser:
                    if isinstance(command, ServerMessage):
                        self.message_signal.maybe_run(writer, command)
                    elif isinstance(command, Ping):
                        self.ping_signal.run(writer, command)  # We always provide one callback
                    elif isinstance(command, ServerJoin):
                        self.join_signal.maybe_run(writer, command)
                    elif isinstance(command, ServerPart):
                        self.part_signal.maybe_run(writer, command)
                    elif isinstance(command, RPLWelcome):
                        self.welcome_signal.maybe_run(writer, command)


class ChannelReader:

    __slots__ = (
        "client_reader",
        "name",
        "room",
        "message_signal",
        "join_signal",
        "part_signal",
    )
    client_reader: ClientReader
    name: str
    room: str
    message_signal: Signal[[ChannelWriter, ServerMessage], object]
    join_signal: Signal[[ChannelWriter, ServerJoin], object]
    part_signal: Signal[[ChannelWriter, ServerPart], object]

    def __init__(self, client_reader: ClientReader, *, name: str) -> None:
        self.client_reader = client_reader
        self.name = name
        self.room = "#" + name
        self.message_signal = Signal()
        self.join_signal = Signal()
        self.part_signal = Signal()

    def add_callbacks(self) -> Self:
        client_reader = self.client_reader
        client_reader.welcome_signal.add_callback(self._on_client_welcome)
        client_reader.message_signal.add_callback(self._on_client_message)
        client_reader.join_signal.add_callback(self._on_client_join)
        client_reader.part_signal.add_callback(self._on_client_part)
        return self

    def remove_callbacks(self) -> Self:
        client_reader = self.client_reader
        client_reader.welcome_signal.remove_callback(self._on_client_welcome)
        client_reader.message_signal.remove_callback(self._on_client_message)
        client_reader.join_signal.remove_callback(self._on_client_join)
        client_reader.part_signal.remove_callback(self._on_client_part)
        return self

    async def connect(self, client: ClientWriter) -> Self:
        await client.join(self.room)
        return self

    async def _on_client_welcome(self, client: ClientWriter, _: RPLWelcome) -> None:
        await client.join(self.room)

    async def _on_client_message(self, client: ClientWriter, message: ServerMessage) -> None:
        if self.room != message.room:
            return
        self.message_signal.maybe_run(
            client.create_channel_writer(self.name),
            message,
        )

    async def _on_client_join(self, client: ClientWriter, join: ServerJoin) -> None:
        if self.room != join.room:
            return
        self.join_signal.maybe_run(
            client.create_channel_writer(self.name),
            join,
        )

    async def _on_client_part(self, client: ClientWriter, part: ServerPart) -> None:
        if self.room != part.room:
            return
        self.part_signal.maybe_run(
            client.create_channel_writer(self.name),
            part,
        )
