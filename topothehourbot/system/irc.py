from __future__ import annotations

__all__ = [
    "IRCv3Client",
    "IRCv3ClientExtension",
    "connect",
]

import asyncio
from abc import ABCMeta
from asyncio import TaskGroup
from collections.abc import AsyncIterator, Coroutine, Iterator
from contextlib import AbstractContextManager
from typing import Any, Final, Optional, Self, final, overload

import ircv3
import websockets
from ircv3 import (IRCv3ClientCommandProtocol, IRCv3Command,
                   IRCv3ServerCommandProtocol, Ping)
from ircv3.dialects.twitch import (ClientJoin, ClientPart,
                                   ClientPrivateMessage, RoomState, ServerJoin,
                                   ServerPart, ServerPrivateMessage,
                                   SupportsClientProperties)
from websockets import ConnectionClosed, WebSocketClientProtocol

from .pipes import Diverter, Pipe


class IRCv3ServerCommandParser(Iterator[IRCv3ServerCommandProtocol]):

    NIL: Final[object] = object()
    END: Final[object] = object()

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
        """The connection latency in milliseconds

        Updated with each ping sent by the underlying connection. Set to ``0``
        before the first ping.
        """
        return self._connection.latency * 1000

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

    async def message(
        self,
        comment: str,
        target: ServerPrivateMessage | str,
        *,
        important: bool = False,
    ) -> Optional[ConnectionClosed]:
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

    async def accumulate(self) -> None:
        async with TaskGroup() as tasks:
            with self.attachment() as pipe:
                async for coro in (
                    aiter(pipe)
                        .filter(ircv3.is_ping)
                        .map(Ping.reply)
                        .map(self.send)
                ):
                    tasks.create_task(coro)

    async def distribute(self) -> None:
        accumulator = asyncio.create_task(self.accumulate())
        with self._diverter.closure() as diverter:
            async for command in self:
                diverter.send(command)
        await accumulator


class IRCv3ClientExtension[AccumulateT, DistributeT](SupportsClientProperties):
    """A wrapper type around an ``IRCv3Client`` or another
    ``IRCv3ClientExtension`` instance with an independent diverter, allowing
    objects of any type to be distributed

    Note that this class does not have a distributor by default. How and when
    distribution occurs is left up to the sub-class implementor.

    This class contains no abstracts.
    """

    type WrappedClientT = IRCv3Client | IRCv3ClientExtension[Any, AccumulateT]

    __slots__ = ("_client", "_diverter")
    _client: WrappedClientT
    _diverter: Diverter[DistributeT]

    @overload
    def __init__(
        self: IRCv3ClientExtension[IRCv3ServerCommandProtocol, DistributeT],
        client: IRCv3Client,
    ) -> None: ...
    @overload
    def __init__(
        self: IRCv3ClientExtension[AccumulateT, DistributeT],
        client: IRCv3ClientExtension[Any, AccumulateT],
    ) -> None: ...

    def __init__(self, client):
        self._client = client
        self._diverter = Diverter()

    @property
    def name(self) -> str:
        """The client's source IRC name"""
        return self._client.name

    @property
    def latency(self) -> float:
        """The connection latency in milliseconds

        Updated with each ping sent by the underlying connection. Set to ``0``
        before the first ping.
        """
        return self._client.latency

    def join(self, *rooms: str) -> Coroutine[Any, Any, Optional[ConnectionClosed]]:
        """Send a JOIN command to the IRC server"""
        return self._client.join(*rooms)

    def part(self, *rooms: str) -> Coroutine[Any, Any, Optional[ConnectionClosed]]:
        """Send a PART command to the IRC server"""
        return self._client.part(*rooms)

    def message(
        self,
        comment: str,
        target: ServerPrivateMessage | str,
        *,
        important: bool = False,
    ) -> Coroutine[Any, Any, Optional[ConnectionClosed]]:
        """Send a PRIVMSG command to the IRC server

        Composes a ``ClientPrivateMessage`` in reply to ``target`` if a
        ``ServerPrivateMessage``, or to the room named by ``target`` if a
        ``str``.

        PRIVMSGs have a global 1.5-second cooldown. ``important`` can be set to
        true to wait for the cooldown, or false to prevent waiting when a
        dispatch occurs during a cooldown period.
        """
        return self._client.message(comment, target, important=important)

    def close(self) -> Coroutine[Any, Any, None]:
        """Close the connection to the IRC server"""
        return self._client.close()

    def until_closure(self) -> Coroutine[Any, Any, None]:
        """Wait until the IRC connection has been closed"""
        return self._client.until_closure()

    def attachment(
        self,
        pipe: Optional[Pipe[DistributeT]] = None,
    ) -> AbstractContextManager[Pipe[DistributeT]]:
        """Return a context manager that safely attaches and detaches ``pipe``

        Default-constructs a ``Pipe`` instance if ``pipe`` is ``None``.
        """
        return self._diverter.attachment(pipe)


async def connect[IRCv3ClientT: IRCv3Client](
    client: type[IRCv3ClientT],
    *,
    oauth_token: str,
) -> AsyncIterator[IRCv3ClientT]:
    """Connect to the Twitch IRC server as ``client``, reconnecting on each
    iteration
    """
    async for connection in websockets.connect("ws://irc-ws.chat.twitch.tv:80"):
        connected_client = client(connection)
        await connected_client.send("CAP REQ :twitch.tv/commands twitch.tv/membership twitch.tv/tags")
        await connected_client.send(f"PASS oauth:{oauth_token}")
        error = await connected_client.send(f"NICK {connected_client.name}")
        if not error:
            yield connected_client
