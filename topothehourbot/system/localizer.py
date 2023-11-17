from __future__ import annotations

__all__ = ["Localizer"]

from abc import ABCMeta, abstractmethod
from asyncio import TaskGroup
from collections.abc import Coroutine, Iterable
from typing import Any, final

from ircv3 import IRCv3ClientCommandProtocol
from ircv3.dialects import twitch
from ircv3.dialects.twitch import ClientJoin, LocalServerCommand

from .client import Client
from .pipes import Diverter

# Pyright will complain about this definition because LocalServerCommand is a
# a PEP 695 alias. Fix is coming soon, see:
# https://github.com/microsoft/pyright/issues/6169

class Localizer(Diverter[LocalServerCommand], metaclass=ABCMeta):  # type: ignore

    __slots__ = ("_client")
    _client: Client

    def __init__(self, client: Client) -> None:
        self._client = client

    @property
    @abstractmethod
    def room(self) -> str:
        raise NotImplementedError

    @property
    @final
    def source_name(self) -> str:
        return self._client.source_name

    @property
    @final
    def latency(self) -> float:
        return self._client.latency

    @final
    def send(self, command: IRCv3ClientCommandProtocol | str) -> Coroutine[Any, Any, None]:
        return self._client.send(command)

    @final
    def close(self) -> Coroutine[Any, Any, None]:
        return self._client.close()

    @final
    def until_closure(self) -> Coroutine[Any, Any, None]:
        return self._client.until_closure()

    async def prelude(self) -> None:
        await self.send(ClientJoin(self.room))

    @abstractmethod
    def interludes(self) -> Iterable[Coroutine[Any, Any, Any]]:
        raise NotImplementedError

    async def postlude(self) -> None:
        return

    @final
    async def run(self) -> None:
        await self.prelude()
        async with TaskGroup() as tasks:
            for todo in self.interludes():
                tasks.create_task(todo)
            with self._client.attachment() as pipe:
                async for command in (
                    aiter(pipe)
                        .filter(twitch.is_local_server_command)
                        .filter(lambda command: command.room == self.room)
                ):
                    for pipe in self.pipes():
                        pipe.send(command)
            for pipe in self.pipes():
                pipe.close()
        await self.postlude()
