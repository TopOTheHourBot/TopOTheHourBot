from __future__ import annotations

__all__ = ["LocalClient"]

from abc import ABCMeta, abstractmethod
from asyncio import TaskGroup
from collections.abc import Coroutine, Iterable
from typing import Any, Protocol, final, overload

from ircv3.dialects import twitch
from ircv3.dialects.twitch import LocalServerCommand, ServerPrivateMessage

from .client import Client
from .pipes import Diverter


@final
class GlobalClientInterface(Protocol):  # For typing purposes only
    @property
    def source_name(self) -> str: ...
    @property
    def room(self) -> str: ...
    @property
    def latency(self) -> float: ...


class LocalClient[GlobalClientT: Client](Diverter[LocalServerCommand], metaclass=ABCMeta):  # type: ignore

    __slots__ = ("_client")
    _client: GlobalClientT

    def __init__(self, client: GlobalClientT) -> None:
        self._client = client

    @property
    @abstractmethod
    def source_name(self) -> str:
        raise NotImplementedError

    @property
    @final
    def room(self) -> str:
        return "#" + self.source_name

    @property
    @final
    def global_client(self) -> GlobalClientInterface:
        return self._client

    def join(self) -> Coroutine[Any, Any, None]:
        """JOIN the localizer room"""
        return self._client.join(self.room)

    def part(self) -> Coroutine[Any, Any, None]:
        """PART the localizer room"""
        return self._client.part(self.room)

    @overload
    async def message(self, to: ServerPrivateMessage, comment: str, /, *, important: bool = False) -> None: ...
    @overload
    async def message(self, comment: str, /, *, important: bool = False) -> None: ...

    def message(self, *args, important=False):
        """Send a PRIVMSG in reply to another message, or to the localizer room

        Composite of ``Client.message()``, see its docstring for more details.
        """
        n = len(args)
        if n == 2:
            message, comment = args
            return self._client.message(
                message,
                comment,
                important=important,
            )
        if n == 1:
            comment, = args
            return self._client.message(
                self.room,
                comment,
                important=important,
            )
        raise TypeError(f"expected 1 or 2 positional arguments, got {n}")

    @final
    def close(self) -> Coroutine[Any, Any, None]:
        return self._client.close()

    @final
    def until_closure(self) -> Coroutine[Any, Any, None]:
        return self._client.until_closure()

    def prelude(self) -> Coroutine[Any, Any, None]:
        return self.join()

    @abstractmethod
    def paraludes(self) -> Iterable[Coroutine[Any, Any, Any]]:
        raise NotImplementedError

    def postlude(self) -> Coroutine[Any, Any, None]:
        return self.part()

    @final
    async def run(self) -> None:
        await self.prelude()
        async with TaskGroup() as tasks:
            for todo in self.paraludes():
                tasks.create_task(todo)
            with self._client.attachment() as pipe:
                room = self.room
                async for command in (
                    aiter(pipe)
                        .filter(twitch.is_local_server_command)
                        .filter(lambda command: command.room == room)
                ):
                    for pipe in self.pipes():
                        pipe.send(command)
            for pipe in self.pipes():
                pipe.close()
        await self.postlude()
