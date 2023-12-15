from __future__ import annotations

__all__ = [
    "IRCv3Client",
    "IRCv3ReferenceClient",
    "IRCv3RoomedClient",
    "connect",
]

import asyncio
import functools
import operator
import os
from abc import ABCMeta, abstractmethod
from asyncio import TaskGroup
from collections.abc import AsyncIterator, Coroutine, Iterator
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Any, Final, Optional, Self, final

import ircv3
import websockets
from ircv3 import (IRCv3ClientCommandProtocol, IRCv3Command,
                   IRCv3ServerCommandProtocol, Ping)
from ircv3.dialects import twitch
from ircv3.dialects.twitch import (ClientJoin, ClientPart,
                                   ClientPrivateMessage, LocalServerCommand,
                                   RoomState, ServerJoin, ServerPart,
                                   ServerPrivateMessage,
                                   SupportsClientProperties)
from websockets import ConnectionClosed, WebSocketClientProtocol

from .pipes import Diverter, Pipe


class IRCv3ServerCommandParser(Iterator[IRCv3ServerCommandProtocol]):

    NIL: Final = object()
    END: Final = object()

    __slots__ = ("_data", "_head")
    _data: str
    _head: int

    def __init__(self, data: str, *, head: int = 0) -> None:
        self._data = data
        self._head = head

    def __iter__(self) -> Self:
        return self

    def __next__(self) -> IRCv3ServerCommandProtocol:
        while (result := self.move_head()) is not self.END:
            if result is self.NIL:
                continue
            assert isinstance(result, IRCv3ServerCommandProtocol)
            return result
        raise StopIteration

    def move_head(self) -> object:
        head = self._head
        if head == -1:
            return self.END
        data = self._data
        next = data.find("\r\n", head)
        if next == -1:
            self._head = next
            return self.END
        command = IRCv3Command.from_string(data[head:next])
        name = command.name
        self._head = next + 2
        if name == "PRIVMSG":
            return ServerPrivateMessage.cast(command)
        elif name == "ROOMSTATE":
            return RoomState.cast(command)
        elif name == "PING":
            return Ping.cast(command)
        elif name == "JOIN":
            return ServerJoin.cast(command)
        elif name == "PART":
            return ServerPart.cast(command)
        return self.NIL


class IRCv3Client(SupportsClientProperties, metaclass=ABCMeta):
    """A wrapper type around a ``websockets.WebSocketClientProtocol`` instance
    that provides a Twitch IRC abstraction layer, and a publisher-subscriber
    model for use by coroutines.

    Note that this class does not provide the means to initiate the IRC
    connection - it only serves to manage the distribution of labour by reading
    from a pre-established connection and fanning messages out to attachments
    via the ``run()`` method. A basic execution may look like this:

    ```
    async for connection in websockets.connect(...):
        client = ClientSubClass(connection)
        async with TaskGroup() as tasks:
            tasks.create_task(foo(client))
            tasks.create_task(bar(client))
            await client.run()
    ```

    Coroutines then have the freedom to subscribe themselves to the client in
    order to receive messages from the server. The recommended way of doing
    so is via the ``attachment()`` method, which builds a ``Pipe`` that is
    elegantly closed and detached when the connection ceases:

    ```
    async def foo(client: Client) -> None:
        with client.attachment() as pipe:  # Detaches pipe on exit
            async for reply in (  # Stops iteration on connection closure
                aiter(pipe)
                    .filter(twitch.is_server_private_message)
                    .filter(lambda message: "hi" in message.comment)
                    .map(lambda message: message.reply("hello!"))
            ):
                await client.send(reply)
    ```

    See ``Assembly``, ``Pipe``, and ``Series`` for more details.
    """

    __slots__ = (
        "_connection",
        "_diverter",
        "_last_message_epoch",
        "_last_join_epoch",
    )

    _connection: WebSocketClientProtocol
    _diverter: Diverter[IRCv3ServerCommandProtocol]
    _last_message_epoch: float
    _last_join_epoch: float

    message_cooldown: Final[float] = 1.5
    join_cooldown: Final[float] = 1.5

    def __init__(self, connection: WebSocketClientProtocol) -> None:
        self._connection = connection
        self._diverter = Diverter()
        self._last_message_epoch = 0
        self._last_join_epoch = 0

    @final
    async def __aiter__(self) -> AsyncIterator[IRCv3ServerCommandProtocol]:
        try:
            while True:
                commands = await self.recv()
                for command in commands:
                    yield command
        except ConnectionClosed:
            return

    @property
    @final
    def latency(self) -> float:
        """The connection latency, in seconds

        Updated with each ping sent by the underlying connection. Set to ``0``
        before the first ping.
        """
        return self._connection.latency

    async def send(self, command: IRCv3ClientCommandProtocol | str, /) -> Optional[ConnectionClosed]:
        """Send a command to the IRC server

        Drops the command and returns ``websockets.ConnectionClosed`` if the
        underlying connection is closed during execution.
        """
        data = str(command)
        try:
            await self._connection.send(data)
        except ConnectionClosed as error:
            return error

    async def recv(self) -> IRCv3ServerCommandParser:
        """Receive a command batch from the IRC server

        Raises ``websockets.ConnectionClosed`` if the underlying connection is
        closed during execution.
        """
        data = await self._connection.recv()
        assert isinstance(data, str)
        return IRCv3ServerCommandParser(data)

    async def join(self, *rooms: str) -> Optional[ConnectionClosed]:
        """Send a JOIN command to the IRC server"""
        curr_join_epoch = asyncio.get_running_loop().time()
        last_join_epoch = self._last_join_epoch
        if last_join_epoch:
            delay = max(self.join_cooldown - (curr_join_epoch - last_join_epoch), 0)
        else:
            delay = 0
        self._last_join_epoch = curr_join_epoch + delay
        if delay:
            await asyncio.sleep(delay)
        return await self.send(ClientJoin(*rooms))

    async def part(self, *rooms: str) -> Optional[ConnectionClosed]:
        """Send a PART command to the IRC server"""
        return await self.send(ClientPart(*rooms))

    async def message(self, comment: str, target: ServerPrivateMessage | str, *, important: bool = False) -> Optional[ConnectionClosed]:
        """Send a PRIVMSG command to the IRC server

        Composes a ``ClientPrivateMessage`` in reply to ``target`` if a
        ``ServerPrivateMessage``, or to the room named by ``target`` if a
        ``str``.

        PRIVMSGs have a global 1.5-second cooldown. ``important`` can be set to
        true to wait for the cooldown, or false to prevent waiting when a
        dispatch occurs during a cooldown period.
        """
        curr_message_epoch = asyncio.get_running_loop().time()
        last_message_epoch = self._last_message_epoch
        if last_message_epoch:
            delay = max(self.message_cooldown - (curr_message_epoch - last_message_epoch), 0)
        else:
            delay = 0

        # Note that the moment at which we set _last_message_epoch is crucial
        # to timing everything correctly, here.
        #
        # If important=True, we must set _last_message_epoch *before* sleeping
        # so that subsequent sends during the cooldown period read back the
        # epoch for the delay calculation above.
        #
        # If important=False, we must set _last_message_epoch, but only if
        # we're allowing the send to happen (i.e., only if there is no delay).

        if important:
            self._last_message_epoch = curr_message_epoch + delay
            if delay:
                await asyncio.sleep(delay)
        else:
            if delay:
                return
            self._last_message_epoch = curr_message_epoch
        if isinstance(target, str):
            command = ClientPrivateMessage(target, comment)
        else:
            command = target.reply(comment)

        return await self.send(command)

    @final
    def close(self) -> Coroutine[Any, Any, None]:
        """Close the connection to the IRC server"""
        return self._connection.close()

    @final
    def until_closure(self) -> Coroutine[Any, Any, None]:
        """Wait until the IRC connection has been closed"""
        return self._connection.wait_closed()

    def attachment(
        self,
        pipe: Optional[Pipe[IRCv3ServerCommandProtocol]] = None,
    ) -> AbstractContextManager[Pipe[IRCv3ServerCommandProtocol]]:
        return self._diverter.attachment(pipe)

    async def distribute(self) -> None:
        diverter = self._diverter
        async with TaskGroup() as tasks:
            async for command in self:
                if ircv3.is_ping(command):
                    coro = self.send(command.reply())
                else:
                    diverter.send(command)
                    continue
                tasks.create_task(coro)
            diverter.close()


@dataclass(slots=True)
class IRCv3ReferenceClient(SupportsClientProperties):

    name: str


class IRCv3RoomedClient(SupportsClientProperties, metaclass=ABCMeta):

    __slots__ = ("_connection", "_diverter")
    _connection: IRCv3Client
    _diverter: Diverter[LocalServerCommand]

    def __init__(self, connection: IRCv3Client) -> None:
        self._connection = connection
        self._diverter = Diverter()

    @property
    @abstractmethod
    def rooming_client(self) -> IRCv3ReferenceClient:
        raise NotImplementedError

    async def message(
        self,
        comment: str,
        target: ServerPrivateMessage | str = "",
        *,
        important: bool = False,
    ) -> Optional[ConnectionClosed]:
        return await self._connection.message(
            comment=comment,
            target=target or self.rooming_client.room,
            important=important,
        )

    def attachment(
        self,
        pipe: Optional[Pipe[LocalServerCommand]] = None,
    ) -> AbstractContextManager[Pipe[LocalServerCommand]]:
        return self._diverter.attachment(pipe)

    async def distribute(self) -> None:
        diverter = self._diverter
        with self._connection.attachment() as pipe:
            async for command in (
                aiter(pipe).filter(twitch.is_local_server_command)
                           .filter(functools.partial(operator.eq, self.rooming_client.room))
            ):
                diverter.send(command)
        diverter.close()


async def connect[IRCv3ClientT: IRCv3Client](
    client_factory: type[IRCv3ClientT],
    *,
    oauth_token: Optional[str] = None,
) -> AsyncIterator[IRCv3ClientT]:
    if oauth_token is None:
        oauth_token = os.getenv("TWITCH_OAUTH_TOKEN")
        if oauth_token is None:
            raise ValueError("Twitch OAuth token not found in environment variables")
    assert isinstance(oauth_token, str)
    async for websockets_connection in websockets.connect("ws://irc-ws.chat.twitch.tv:80"):
        connection = client_factory(websockets_connection)
        await connection.send("CAP REQ :twitch.tv/commands twitch.tv/membership twitch.tv/tags")
        await connection.send(f"PASS oauth:{oauth_token}")
        error = await connection.send(f"NICK {connection.name}")
        if not error:
            yield connection
