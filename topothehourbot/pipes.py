from __future__ import annotations

__all__ = [
    "Pipe",
    "Transport",
]

from abc import abstractmethod
from asyncio import TaskGroup
from collections.abc import Coroutine, Iterable
from typing import Any, Final, Protocol, override

import aiosqlite as sqlite
from channels import (Channel, SendOnlyLimiter, SupportsRecv, SupportsSend,
                      SupportsSendAndRecv, Signal)
from ircv3 import IRCv3CommandProtocol
from ircv3.dialects import twitch
from ircv3.dialects.twitch import ClientJoin, ClientPrivmsg
from websockets import client as websockets

from .channels import IRCv3Stream, SQLiteChannel, SQLStream, TwitchChannel

type CommonCommandStream = SupportsSendAndRecv[IRCv3CommandProtocol, IRCv3CommandProtocol]

type ServerCommandStream = SupportsRecv[IRCv3CommandProtocol]

type ClientQueryStream = SQLStream
type ClientJoinStream = SupportsSend[ClientJoin | str]
type ClientMessageStream = SupportsSend[ClientPrivmsg | str]
type ClientCommandStream = IRCv3Stream


class Pipe(Protocol):

    @abstractmethod
    def open(
        self,
        client_queries: ClientQueryStream,
        client_joins: ClientJoinStream,
        client_messages: ClientMessageStream,
        client_commands: ClientCommandStream,
        /,
    ) -> Coroutine[Any, Any, Any]:
        raise NotImplementedError

    @abstractmethod
    def flux(
        self,
        server_commands: ServerCommandStream,
        client_queries: ClientQueryStream,
        client_joins: ClientJoinStream,
        client_messages: ClientMessageStream,
        client_commands: ClientCommandStream,
        /,
    ) -> Coroutine[Any, Any, Any]:
        raise NotImplementedError


class UserPipe(Pipe, Protocol):

    URI: Final[str] = "ws://irc-ws.chat.twitch.tv:80"

    JOIN_COOLDOWN: Final[float]    = 1.5
    MESSAGE_COOLDOWN: Final[float] = 1.5

    @property
    @abstractmethod
    def user(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def access_token(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def outputs(self) -> Iterable[Pipe]:
        raise NotImplementedError

    @override
    async def open(
        self,
        client_queries: ClientQueryStream,
        client_joins: ClientJoinStream,
        client_messages: ClientMessageStream,
        client_commands: ClientCommandStream,
        /,
    ) -> None:
        await client_commands.send("CAP REQ :twitch.tv/membership twitch.tv/tags twitch.tv/commands")
        await client_commands.send(f"PASS oauth:{self.access_token}")
        await client_commands.send(f"NICK {self.user}")

    @override
    async def flux(
        self,
        server_commands: ServerCommandStream,
        client_queries: ClientQueryStream,
        client_joins: ClientJoinStream,
        client_messages: ClientMessageStream,
        client_commands: ClientCommandStream,
        /,
    ) -> None:
        transports = [
            Transport(
                output,
                client_queries=client_queries,
                client_joins=client_joins,
                client_messages=client_messages,
                client_commands=client_commands,
            )
            for output in self.outputs()
        ]

        async with TaskGroup() as tasks:
            for transport in transports:
                tasks.create_task(transport.open())

        async with TaskGroup() as tasks:
            for transport in transports:
                tasks.create_task(transport.flux())
            async for command in server_commands:
                for transport in transports:
                    tasks.create_task(transport.send(command))
            for transport in transports:
                tasks.create_task(transport.send(Signal.STOP))

    async def run(self) -> None:
        async with sqlite.connect(f"{self.user}.db", autocommit=True) as sql_connection:
            async for irc_connection in websockets.connect(self.URI):

                common_commands = TwitchChannel(irc_connection)
                transport = Transport(
                    self,
                    client_queries=SQLiteChannel(sql_connection),
                    client_joins=SendOnlyLimiter(common_commands, cooldown=self.JOIN_COOLDOWN),
                    client_messages=SendOnlyLimiter(common_commands, cooldown=self.MESSAGE_COOLDOWN),
                    client_commands=common_commands,
                )

                await transport.open()

                async with TaskGroup() as tasks:
                    tasks.create_task(transport.flux())
                    async for commands in common_commands:
                        for command in commands:
                            if twitch.is_ping(command):
                                tasks.create_task(common_commands.send(command.reply()))
                                continue
                            tasks.create_task(transport.send(command))
                    await transport.send(Signal.STOP)


class RoomPipe(Pipe, Protocol):

    @property
    @abstractmethod
    def room(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def outputs(self) -> Iterable[Pipe]:
        raise NotImplementedError

    @override
    async def open(
        self,
        client_queries: ClientQueryStream,
        client_joins: ClientJoinStream,
        client_messages: ClientMessageStream,
        client_commands: ClientCommandStream,
        /,
    ) -> None:
        await client_joins.send(ClientJoin(self.room))

    @override
    async def flux(
        self,
        server_commands: ServerCommandStream,
        client_queries: ClientQueryStream,
        client_joins: ClientJoinStream,
        client_messages: ClientMessageStream,
        client_commands: ClientCommandStream,
        /,
    ) -> None:
        client_messages = SendOnlyLimiter(client_messages)
        transports = [
            Transport(
                output,
                client_queries=client_queries,
                client_joins=client_joins,
                client_messages=client_messages,
                client_commands=client_commands,
            )
            for output in self.outputs()
        ]

        async with TaskGroup() as tasks:
            for transport in transports:
                tasks.create_task(transport.open())

        async with TaskGroup() as tasks:
            for transport in transports:
                tasks.create_task(transport.flux())
            async for command in (
                server_commands
                    .recv_each()
                    .filter(twitch.is_local)
                    .filter(lambda command: command.room == self.room)
            ):
                if twitch.is_room_state(command):
                    if (delay := command.delay) is not None:
                        client_messages.cooldown = delay
                    continue
                for transport in transports:
                    tasks.create_task(transport.send(command))
            for transport in transports:
                tasks.create_task(transport.send(Signal.STOP))


class Transport[
    PipeT: Pipe,
    ClientQueryStreamT: ClientQueryStream,
    ClientJoinStreamT: ClientJoinStream,
    ClientMessageStreamT: ClientMessageStream,
    ClientCommandStreamT: ClientCommandStream,
](SupportsSend[IRCv3CommandProtocol]):

    __slots__ = (
        "_pipe",
        "_server_commands",
        "_client_queries",
        "_client_joins",
        "_client_messages",
        "_client_commands",
    )
    _pipe: PipeT
    _server_commands: CommonCommandStream
    _client_queries: ClientQueryStreamT
    _client_joins: ClientJoinStreamT
    _client_messages: ClientMessageStreamT
    _client_commands: ClientCommandStreamT

    def __init__(
        self,
        pipe: PipeT,
        *,
        client_queries: ClientQueryStreamT,
        client_joins: ClientJoinStreamT,
        client_messages: ClientMessageStreamT,
        client_commands: ClientCommandStreamT,
    ) -> None:
        self._pipe = pipe
        self._server_commands = Channel[IRCv3CommandProtocol]()
        self._client_queries = client_queries
        self._client_joins = client_joins
        self._client_messages = client_messages
        self._client_commands = client_commands

    @property
    def pipe(self) -> PipeT:
        return self._pipe

    @property
    def client_queries(self) -> ClientQueryStreamT:
        return self._client_queries

    @property
    def client_joins(self) -> ClientJoinStreamT:
        return self._client_joins

    @property
    def client_messages(self) -> ClientMessageStreamT:
        return self._client_messages

    @property
    def client_commands(self) -> ClientCommandStreamT:
        return self._client_commands

    @override
    def send(self, command: IRCv3CommandProtocol | Signal) -> Coroutine[Any, Any, Any]:
        return self._server_commands.send(command)

    def open(self) -> Coroutine[Any, Any, Any]:
        return self.pipe.open(
            self.client_queries,
            self.client_joins,
            self.client_messages,
            self.client_commands,
        )

    def flux(self) -> Coroutine[Any, Any, Any]:
        return self.pipe.flux(
            self._server_commands,
            self.client_queries,
            self.client_joins,
            self.client_messages,
            self.client_commands,
        )
