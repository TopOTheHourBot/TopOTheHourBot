from __future__ import annotations

__all__ = ["SubClient"]

from abc import ABCMeta, abstractmethod
from asyncio import TaskGroup
from collections.abc import Coroutine, Iterable
from typing import Any, Optional, final

from ircv3 import IRCv3ServerCommandProtocol
from ircv3.dialects.twitch import (ServerPrivateMessage,
                                   SupportsClientProperties)

from .client import Client
from .pipes import Diverter


class SubClient[ClientT: Client, ValueT](Diverter[ValueT], metaclass=ABCMeta):

    __slots__ = ("_client")
    _client: ClientT

    def __init__(self, client: ClientT) -> None:
        self._client = client

    @property
    @final
    def client(self) -> SupportsClientProperties:
        """The superior client"""
        return self._client

    def join(self, *rooms: str) -> Coroutine[Any, Any, None]:
        """Send a JOIN command to the IRC server"""
        return self._client.join(*rooms)

    def part(self, *rooms: str) -> Coroutine[Any, Any, None]:
        """Send a PART command to the IRC server"""
        return self._client.part(*rooms)

    def message(
        self,
        target: ServerPrivateMessage | str,
        comment: str,
        *,
        important: bool = False,
    ) -> Coroutine[Any, Any, None]:
        """Send a PRIVMSG command to the IRC server"""
        return self._client.message(target, comment, important=important)

    @final
    def close(self) -> Coroutine[Any, Any, None]:
        """Close the connection to the IRC server"""
        return self._client.close()

    @final
    def until_closure(self) -> Coroutine[Any, Any, None]:
        """Wait until the IRC connection has been closed"""
        return self._client.until_closure()

    @abstractmethod
    def mapper(self, command: IRCv3ServerCommandProtocol, /) -> Optional[ValueT]:
        raise NotImplementedError

    async def prelude(self) -> Any:
        """Coroutine executed before the main distribution loop

        Takes no action by default.
        """
        return

    def paraludes(self) -> Iterable[Coroutine[Any, Any, Any]]:
        """Coroutines executed in parallel with the main distribution loop

        Returns no coroutines by default.
        """
        return ()

    async def postlude(self) -> Any:
        """Coroutine executed after the main distribution loop

        Takes no action by default.
        """
        return

    @final
    async def run(self) -> None:
        await self.prelude()
        async with TaskGroup() as tasks:
            for coro in self.paraludes():
                tasks.create_task(coro)
            with self._client.attachment() as pipe:
                async for command in (
                    aiter(pipe)
                        .map(self.mapper)
                        .not_none()
                ):
                    for pipe in self.pipes():
                        pipe.send(command)
            for pipe in self.pipes():
                pipe.close()
        await self.postlude()
