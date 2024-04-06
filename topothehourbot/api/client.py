from __future__ import annotations

__all__ = [
    "ClientReader",
    "ClientWriter",
    "ChannelReader",
    "ChannelWriter",
]

import asyncio
from collections import defaultdict
from typing import ClassVar, Final

import websockets
from ircv3 import Ping, RPLWelcome
from ircv3.dialects.twitch import (ClientJoin, ClientMessage, ClientPart,
                                   ServerJoin, ServerMessage, ServerPart)
from websockets import WebSocketClientProtocol

from .parser import ServerCommandParser
from .utilities import Signal


class ClientReader:

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
    )
    oauth_token: str
    name: str
    welcome_signal: Signal[[ClientWriter, RPLWelcome], object]
    ping_signal: Signal[[ClientWriter, Ping], object]
    message_signal: Signal[[ClientWriter, ServerMessage], object]
    join_signal: Signal[[ClientWriter, ServerJoin], object]
    part_signal: Signal[[ClientWriter, ServerPart], object]

    def __init__(self, *, oauth_token: str, name: str) -> None:
        self.oauth_token = oauth_token
        self.name = name
        self.room = "#" + name
        self.welcome_signal = Signal()
        self.ping_signal = Signal().add_callback(self._on_client_ping)
        self.message_signal = Signal()
        self.join_signal = Signal()
        self.part_signal = Signal()

    async def _on_client_ping(self, writer: ClientWriter, command: Ping) -> None:
        await writer.send(command.reply())

    async def read(self):
        async for websocket in websockets.connect(self.uri):
            writer = ClientWriter(self, websocket)
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
        "name",
        "room",
        "message_signal",
        "join_signal",
        "part_signal",
    )
    name: str
    room: str
    message_signal: Signal[[ChannelWriter, ServerMessage], object]
    join_signal: Signal[[ChannelWriter, ServerJoin], object]
    part_signal: Signal[[ChannelWriter, ServerPart], object]

    def __init__(self, *, name: str) -> None:
        self.name = name
        self.room = "#" + name
        self.message_signal = Signal()
        self.join_signal = Signal()
        self.part_signal = Signal()

    # def add_callbacks(self) -> Self:
    #     client_reader = self.client_reader
    #     client_reader.welcome_signal.add_callback(self._on_client_welcome)
    #     client_reader.message_signal.add_callback(self._on_client_message)
    #     client_reader.join_signal.add_callback(self._on_client_join)
    #     client_reader.part_signal.add_callback(self._on_client_part)
    #     return self

    # def remove_callbacks(self) -> Self:
    #     client_reader = self.client_reader
    #     client_reader.welcome_signal.remove_callback(self._on_client_welcome)
    #     client_reader.message_signal.remove_callback(self._on_client_message)
    #     client_reader.join_signal.remove_callback(self._on_client_join)
    #     client_reader.part_signal.remove_callback(self._on_client_part)
    #     return self

    async def _on_client_welcome(self, writer: ClientWriter, command: RPLWelcome) -> None:
        await writer.join(self.room)

    async def _on_client_message(self, writer: ClientWriter, command: ServerMessage) -> None:
        if self.room != command.room:
            return
        self.message_signal.maybe_run(
            ChannelWriter(self, writer),
            command,
        )

    async def _on_client_join(self, writer: ClientWriter, command: ServerJoin) -> None:
        if self.room != command.room:
            return
        self.join_signal.maybe_run(
            ChannelWriter(self, writer),
            command,
        )

    async def _on_client_part(self, writer: ClientWriter, command: ServerPart) -> None:
        if self.room != command.room:
            return
        self.part_signal.maybe_run(
            ChannelWriter(self, writer),
            command,
        )


class ClientWriter:

    # These are strictly accessed as class variables to ensure that, no matter
    # the instance, all will be working with the same cooldowns and epochs.

    _message_cooldowns: ClassVar[defaultdict[str, float]] = defaultdict(lambda: 1.5)
    """A mapping of client names to their respective PRIVMSG cooldowns

    Defaults to 1.5 seconds, allowing 20 messages to be sent every 30 seconds
    (the standard Twitch rate limit).
    """
    _join_cooldowns: ClassVar[defaultdict[str, float]] = defaultdict(lambda: 1.5)
    """A mapping of client names to their respective JOIN cooldowns

    Defaults to 1.5 seconds, allowing 20 joins to be sent every 30 seconds (the
    standard Twitch rate limit).
    """
    _last_message_epochs: ClassVar[defaultdict[str, float]] = defaultdict(lambda: 0)
    """A mapping of client names to the times at which they last sent a PRIVMSG

    Set to 0 if the client has not sent a PRIVMSG.
    """
    _last_join_epochs: ClassVar[defaultdict[str, float]] = defaultdict(lambda: 0)
    """A mapping of client names to the times at which they last sent a JOIN

    Set to 0 if the client has not sent a JOIN.
    """

    __slots__ = ("reader", "writer")
    reader: ClientReader
    writer: WebSocketClientProtocol

    def __init__(
        self,
        reader: ClientReader,
        writer: WebSocketClientProtocol,
    ) -> None:
        super().__init__()
        self.reader = reader
        self.writer = writer

    @property
    def name(self) -> str:
        return self.reader.name

    @property
    def room(self) -> str:
        return self.reader.room

    @property
    def latency(self) -> float:
        """The websocket latency, in milliseconds

        Set to 0 if the websocket has not sent a ping.
        """
        return self.writer.latency * 1000

    @property
    def message_cooldown(self) -> float:
        """The client's PRIVMSG cooldown, in seconds

        Defaults to 1.5, allowing 20 messages to be sent every 30 seconds (the
        standard rate limit).

        Note that setting this property will modify the message cooldown for
        all ``ClientWriter`` instances of the same name.
        """
        return ClientWriter._message_cooldowns[self.name]

    @message_cooldown.setter
    def message_cooldown(self, cooldown: float) -> None:
        ClientWriter._message_cooldowns[self.name] = cooldown

    @property
    def join_cooldown(self) -> float:
        """The client's JOIN cooldown, in seconds

        Defaults to 1.5, allowing 20 joins to be sent every 30 seconds (the
        standard rate limit).

        Note that setting this property will modify the join cooldown for all
        ``ClientWriter`` instances of the same name.
        """
        return ClientWriter._join_cooldowns[self.name]

    @join_cooldown.setter
    def join_cooldown(self, cooldown: float) -> None:
        ClientWriter._join_cooldowns[self.name] = cooldown

    @property
    def last_message_epoch(self) -> float:
        """The time at which the last PRIVMSG was sent, respective to the
        running event loop

        Set to 0 if the client has not sent a PRIVMSG.
        """
        return ClientWriter._last_message_epochs[self.name]

    @property
    def last_join_epoch(self) -> float:
        """The time at which the last JOIN was sent, respective to the running
        event loop

        Set to 0 if the client has not sent a JOIN.
        """
        return ClientWriter._last_join_epochs[self.name]

    async def send(self, command: object, /) -> None:
        data = str(command)
        await self.writer.send(data)

    async def message(
        self,
        comment: object,
        target: ServerMessage | str,
        *,
        important: bool = True,
    ) -> None:
        name = self.name
        curr_message_epoch = asyncio.get_running_loop().time()
        last_message_epoch = ClientWriter._last_message_epochs[name]
        if last_message_epoch:
            delay = max(
                ClientWriter._message_cooldowns[name]
                - (curr_message_epoch - last_message_epoch),
                0,
            )
        else:
            delay = 0
        if important:
            ClientWriter._last_message_epochs[name] = curr_message_epoch + delay
            if delay:
                await asyncio.sleep(delay)
        else:
            if delay:
                return
            ClientWriter._last_message_epochs[name] = curr_message_epoch
        comment = str(comment)
        command = ClientMessage(target, comment) if isinstance(target, str) else target.reply(comment)
        return await self.send(command)

    async def join(self, *rooms: str) -> None:
        name = self.name
        curr_join_epoch = asyncio.get_running_loop().time()
        last_join_epoch = ClientWriter._last_join_epochs[name]
        if last_join_epoch:
            delay = max(
                ClientWriter._join_cooldowns[name]
                - (curr_join_epoch - last_join_epoch),
                0,
            )
        else:
            delay = 0
        ClientWriter._last_join_epochs[name] = curr_join_epoch + delay
        if delay:
            await asyncio.sleep(delay)
        return await self.send(ClientJoin(*rooms))

    async def part(self, *rooms: str) -> None:
        return await self.send(ClientPart(*rooms))

    async def close(self) -> None:
        await self.writer.close()


class ChannelWriter:

    __slots__ = ("reader", "writer")
    reader: ChannelReader
    writer: ClientWriter

    def __init__(
        self,
        reader: ChannelReader,
        writer: ClientWriter,
    ) -> None:
        self.reader = reader
        self.writer = writer

    @property
    def name(self) -> str:
        return self.reader.name

    @property
    def room(self) -> str:
        return self.reader.room

    async def message(
        self,
        comment: object,
        target: ServerMessage | str = "#",
        *,
        important: bool = True,
    ) -> None:
        await self.writer.message(
            comment,
            self.room if target == "#" else target,
            important=important,
        )
