from __future__ import annotations

__all__ = ["SubClient"]

from abc import ABCMeta, abstractmethod
from asyncio import TaskGroup
from collections.abc import Coroutine, Iterable
from typing import Any, Optional, final

from ircv3 import IRCv3ServerCommandProtocol
from ircv3.dialects.twitch import ServerPrivateMessage

from .client import Client
from .pipes import Diverter

type SourceClient = Client | SubClient


class SubClient[SourceClientT: SourceClient, ValueT](Diverter[ValueT], metaclass=ABCMeta):

    __slots__ = ("_source_client")
    _source_client: SourceClientT

    def __init__(self, source_client: SourceClientT) -> None:
        self._source_client = source_client

    @property
    @final
    def source_client(self) -> SourceClientT:
        """The source client"""
        return self._source_client

    def join(self, *rooms: str) -> Coroutine[Any, Any, None]:
        """Send a JOIN command to the IRC server"""
        return self._source_client.join(*rooms)

    def part(self, *rooms: str) -> Coroutine[Any, Any, None]:
        """Send a PART command to the IRC server"""
        return self._source_client.part(*rooms)

    def message(
        self,
        target: ServerPrivateMessage | str,
        comment: str,
        *,
        important: bool = False,
    ) -> Coroutine[Any, Any, None]:
        """Send a PRIVMSG command to the IRC server"""
        return self._source_client.message(target, comment, important=important)

    @final
    def close(self) -> Coroutine[Any, Any, None]:
        """Close the connection to the IRC server"""
        return self._source_client.close()

    @final
    def until_closure(self) -> Coroutine[Any, Any, None]:
        """Wait until the IRC connection has been closed"""
        return self._source_client.until_closure()

    @abstractmethod
    def mapper(self, command: IRCv3ServerCommandProtocol, /) -> Optional[ValueT]:
        """Return the ``command`` as a new value, or ``None`` if no such
        conversion is possible
        """
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
            with self._source_client.attachment() as pipe:
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
