from __future__ import annotations

__all__ = ["Client"]

import asyncio
import contextlib
from abc import ABCMeta, abstractmethod
from asyncio import TaskGroup
from collections.abc import AsyncIterator, Coroutine, Iterable, Iterator
from typing import Any, Final, Literal, final

import ircv3
from ircv3 import (IRCv3ClientCommandProtocol, IRCv3Command,
                   IRCv3ServerCommandProtocol, Ping)
from ircv3.dialects import twitch
from ircv3.dialects.twitch import (RoomState, ServerJoin, ServerPart,
                                   ServerPrivateMessage)
from websockets import ConnectionClosed, WebSocketClientProtocol

from .pipes import Diverter

CRLF: Final[Literal["\r\n"]] = "\r\n"


class Client(Diverter[IRCv3ServerCommandProtocol], metaclass=ABCMeta):
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

    See ``Diverter``, ``Pipe``, and ``Series`` for more details.
    """

    __slots__ = ("_connection", "_last_message_time")
    _connection: WebSocketClientProtocol
    _last_message_time: float
    message_cooldown: Final[float] = 1.5

    def __init__(self, connection: WebSocketClientProtocol) -> None:
        self._connection = connection
        self._last_message_time = 0

    @final
    def _parse_commands(self, data: str) -> Iterator[IRCv3ServerCommandProtocol]:
        raw_commands = data.removesuffix(CRLF).split(CRLF)
        for command in map(IRCv3Command.from_string, raw_commands):
            name = command.name
            if name == "PRIVMSG":
                yield ServerPrivateMessage.cast(command)
            elif name == "ROOMSTATE":
                yield RoomState.cast(command)
            elif name == "PING":
                yield Ping.cast(command)
            elif name == "JOIN":
                yield ServerJoin.cast(command)
            elif name == "PART":
                yield ServerPart.cast(command)

    @final
    async def __aiter__(self) -> AsyncIterator[IRCv3ServerCommandProtocol]:
        while True:
            data = await self._connection.recv()
            assert isinstance(data, str)
            for command in self._parse_commands(data):
                yield command

    @property
    @abstractmethod
    def source_name(self) -> str:
        """The client source name"""
        raise NotImplementedError

    @property
    @abstractmethod
    def oauth_token(self) -> str:
        """The client OAuth token"""
        raise NotImplementedError

    @property
    @final
    def latency(self) -> float:
        """The connection latency, in seconds

        Updated with each ping sent by the underlying connection. Set to ``0``
        before the first ping.
        """
        return self._connection.latency

    @final
    async def send(self, command: IRCv3ClientCommandProtocol, *, important: bool = False) -> None:
        """Send a command to the IRC server

        Awaits or refuses to send ``ClientPrivateMessage``s if dispatched
        during the cooldown period while ``important`` is true or false,
        respectively.
        """
        if twitch.is_client_private_message(command):
            curr_message_time = asyncio.get_running_loop().time()
            last_message_time = self._last_message_time or curr_message_time
            delay = max(
                self.message_cooldown
                - (curr_message_time - last_message_time),
                0,
            )
            if delay > 0:
                if not important:
                    return
                self._last_message_time = curr_message_time + delay
                await asyncio.sleep(delay)
        data = str(command)
        with contextlib.suppress(ConnectionClosed):
            await self._connection.send(data)

    @final
    def close(self) -> Coroutine[Any, Any, None]:
        """Close the connection to the IRC server"""
        return self._connection.close()

    @final
    def until_closure(self) -> Coroutine[Any, Any, None]:
        """Wait until the connection has been closed"""
        return self._connection.wait_closed()

    async def prelude(self) -> None:
        """Coroutine executed before the main distribution loop"""
        connection = self._connection
        try:
            await connection.send("CAP REQ :twitch.tv/commands twitch.tv/membership twitch.tv/tags")
            await connection.send(f"PASS oauth:{self.oauth_token}")
            await connection.send(f"NICK {self.source_name}")
        except ConnectionClosed:
            return

    @abstractmethod
    def paraludes(self) -> Iterable[Coroutine[Any, Any, Any]]:
        """Coroutines executed in parallel with the main distribution loop

        Note that coroutines returned by this method are expected to end when
        the client connection closes. For coroutines that simply attach
        themselves and read from the emitted pipe, such as this one:

        ```
        async def foo(client: Client) -> None:
            with client.attachment() as pipe:
                async for command in pipe:
                    print(command)
        ```

        Closure is already accounted for by the attachment - the ``Pipe``
        object will end iteration when the connection closes.

        For detached coroutines, you can block until closure by using the
        ``until_closure()`` method:

        ```
        async def bar(client: Client) -> None:
            task = asyncio.create_task(foo(client))
            await client.until_closure()
            await task
        ```
        """
        raise NotImplementedError

    async def postlude(self) -> None:
        """Coroutine executed after the main distribution loop"""
        return

    @final
    async def run(self) -> None:
        """Perpetually read and fan server messages out to attachments until
        the connection closes.

        All pipes attached at the moment of closure will be closed. ``Ping``
        commands are withheld from distribution.
        """
        await self.prelude()
        async with TaskGroup() as tasks:
            for todo in self.paraludes():
                tasks.create_task(todo)
            try:
                async for command in self:
                    if ircv3.is_ping(command):
                        todo = self.send(command.reply())
                    else:
                        for pipe in self.pipes():
                            pipe.send(command)
                        continue
                    tasks.create_task(todo)
            except ConnectionClosed:
                pass
            finally:
                for pipe in self.pipes():
                    pipe.close()
        await self.postlude()
