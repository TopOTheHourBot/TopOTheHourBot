from __future__ import annotations

__all__ = ["Client"]

import asyncio
from abc import ABCMeta, abstractmethod
from asyncio import TaskGroup
from collections.abc import AsyncIterator, Coroutine, Iterable, Iterator
from typing import Any, Final, Literal, final

import ircv3
from ircv3 import (IRCv3ClientCommandProtocol, IRCv3Command,
                   IRCv3ServerCommandProtocol, Ping)
from ircv3.dialects.twitch import (ClientJoin, ClientPart,
                                   ClientPrivateMessage, RoomState, ServerJoin,
                                   ServerPart, ServerPrivateMessage,
                                   SupportsClientProperties)
from websockets import ConnectionClosed, WebSocketClientProtocol

from .pipes import Diverter

CRLF: Final[Literal["\r\n"]] = "\r\n"


class Client(
    Diverter[IRCv3ServerCommandProtocol],
    SupportsClientProperties,
    metaclass=ABCMeta,
):
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

    __slots__ = ("_connection", "_last_message_epoch", "_last_join_epoch")

    _connection: WebSocketClientProtocol
    _last_message_epoch: float
    _last_join_epoch: float

    message_cooldown: Final[float] = 1.5
    join_cooldown: Final[float] = 1.5

    def __init__(self, connection: WebSocketClientProtocol) -> None:
        self._connection = connection
        self._last_message_epoch = 0
        self._last_join_epoch = 0

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
    def oauth_token(self) -> str:
        """The client's OAuth token"""
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
    async def send(self, command: IRCv3ClientCommandProtocol | str, /) -> None:
        """Send a command to the IRC server

        Drops the command if the connection is closed during execution.
        """
        data = str(command)
        try:
            await self._connection.send(data)
        except ConnectionClosed:
            return

    async def join(self, *rooms: str) -> None:
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
        await self.send(ClientJoin(*rooms))

    async def part(self, *rooms: str) -> None:
        """Send a PART command to the IRC server"""
        await self.send(ClientPart(*rooms))

    async def message(
        self,
        target: ServerPrivateMessage | str,
        comment: str,
        *,
        important: bool = False,
    ) -> None:
        """Send a PRIVMSG command to the IRC server

        Composes a ``ClientPrivateMessage`` in reply to ``target`` if a
        ``ServerPrivateMessage``, or to the channel named by ``target`` if a
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

        await self.send(command)

    @final
    def close(self) -> Coroutine[Any, Any, None]:
        """Close the connection to the IRC server"""
        return self._connection.close()

    @final
    def until_closure(self) -> Coroutine[Any, Any, None]:
        """Wait until the IRC connection has been closed"""
        return self._connection.wait_closed()

    async def prelude(self) -> Any:
        """Coroutine executed before the main distribution loop

        Authenticates and requests capabilities from the IRC server by default.
        """
        await self.send("CAP REQ :twitch.tv/commands twitch.tv/membership twitch.tv/tags")
        await self.send(f"PASS oauth:{self.oauth_token}")
        await self.send(f"NICK {self.name}")

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
        return ()

    async def postlude(self) -> Any:
        """Coroutine executed after the main distribution loop

        Takes no action by default.
        """
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
            for coro in self.paraludes():
                tasks.create_task(coro)
            try:
                async for command in self:
                    if ircv3.is_ping(command):
                        coro = self.send(command.reply())
                    else:
                        for pipe in self.pipes():
                            pipe.send(command)
                        continue
                    tasks.create_task(coro)
            except ConnectionClosed:
                pass
            finally:
                for pipe in self.pipes():
                    pipe.close()
        await self.postlude()
