from __future__ import annotations

__all__ = ["Client"]

import asyncio
import logging
from abc import ABCMeta
from asyncio import TaskGroup
from collections.abc import AsyncIterator, Coroutine
from contextlib import AbstractContextManager
from typing import Any, Final, Optional

import ircv3
from channels import Channel, Diverter
from ircv3 import ClientCommandProtocol, Ping, ServerCommandProtocol
from ircv3.dialects.twitch import (ClientJoin, ClientPart,
                                   ClientPrivateMessage, ServerPrivateMessage,
                                   SupportsClientProperties)
from websockets import ConnectionClosed, WebSocketClientProtocol

from .parser import ServerCommandParser


class Client(SupportsClientProperties, metaclass=ABCMeta):

    __slots__ = (
        "_connection",
        "_diverter",
        "_last_message_epoch",
        "_last_join_epoch",
    )

    _connection: WebSocketClientProtocol
    _diverter: Diverter[ServerCommandProtocol]
    _last_message_epoch: float
    _last_join_epoch: float

    message_cooldown: Final[float] = 1.5
    join_cooldown: Final[float] = 1.5

    def __init__(self, connection: WebSocketClientProtocol) -> None:
        self._connection = connection
        self._diverter = Diverter()
        self._last_message_epoch = 0
        self._last_join_epoch = 0

    async def __aiter__(self) -> AsyncIterator[ServerCommandProtocol]:
        try:
            while True:
                commands = await self.recv()
                for command in commands:
                    yield command
        except ConnectionClosed:
            logging.exception("Connection closed during perpetual reception")
            return

    @property
    def latency(self) -> float:
        """The connection latency in milliseconds

        Updated with each ping sent by the underlying connection. Set to ``0``
        before the first ping.
        """
        return self._connection.latency * 1000

    async def send(self, command: ClientCommandProtocol | str, /) -> Optional[ConnectionClosed]:
        """Send a command to the IRC server

        Drops the command and returns ``websockets.ConnectionClosed`` if the
        underlying connection is closed during execution.
        """
        data = str(command)
        try:
            await self._connection.send(data)
        except ConnectionClosed as error:
            return error

    async def recv(self) -> ServerCommandParser:
        """Receive a command batch from the IRC server

        Raises ``websockets.ConnectionClosed`` if the underlying connection is
        closed during execution.
        """
        data = await self._connection.recv()
        assert isinstance(data, str)
        return ServerCommandParser(data)

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
        important: bool = True,
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

    def close(self) -> Coroutine[Any, Any, None]:
        """Close the connection to the IRC server"""
        return self._connection.close()

    def until_closure(self) -> Coroutine[Any, Any, None]:
        """Wait until the IRC connection has been closed"""
        return self._connection.wait_closed()

    def attachment(
        self,
        channel: Optional[Channel[ServerCommandProtocol]] = None,
    ) -> AbstractContextManager[Channel[ServerCommandProtocol]]:
        """Return a context manager that safely attaches and detaches
        ``channel``

        Default-constructs a ``Channel`` instance if ``channel`` is ``None``.
        """
        return self._diverter.attachment(channel)

    async def accumulate(self) -> None:
        async with TaskGroup() as tasks:
            with self.attachment() as channel:
                async for coro in (
                    aiter(channel)
                        .filter(ircv3.is_ping)
                        .map(Ping.reply)
                        .map(self.send)
                ):
                    tasks.create_task(coro)

    async def distribute(self) -> None:
        async with TaskGroup() as tasks:
            tasks.create_task(self.accumulate())
            with self._diverter.closure() as diverter:
                async for command in self:
                    diverter.send(command)
