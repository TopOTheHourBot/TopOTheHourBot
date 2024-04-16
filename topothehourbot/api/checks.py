from __future__ import annotations

__all__ = ["walled", "roomed"]

from collections.abc import Callable, Coroutine
from typing import Any

from ircv3.twitch import ServerJoin, ServerMessage, ServerPart

from .client import ClientWriter

type RoomedCommand = ServerMessage | ServerJoin | ServerPart


def walled[
    ResultT: Coroutine[Any, Any, object] | None,
]() -> Callable[[Callable[[ClientWriter, ServerMessage], ResultT]], Callable[[ClientWriter, ServerMessage], ResultT | None]]:

    def walled_decorator(callback: Callable[[ClientWriter, ServerMessage], ResultT]) -> Callable[[ClientWriter, ServerMessage], ResultT | None]:

        def walled_wrapper(writer: ClientWriter, command: ServerMessage) -> ResultT | None:
            if writer.client.name == command.sender.name:
                return
            return callback(writer, command)

        walled_wrapper.__name__ = callback.__name__
        walled_wrapper.__doc__ = callback.__doc__

        return walled_wrapper

    return walled_decorator


def roomed[
    CommandT: RoomedCommand,
    ResultT: Coroutine[Any, Any, object] | None,
](*rooms: str) -> Callable[[Callable[[ClientWriter, CommandT], ResultT]], Callable[[ClientWriter, CommandT], ResultT | None]]:
    set = frozenset(rooms)

    def roomed_decorator(callback: Callable[[ClientWriter, CommandT], ResultT]) -> Callable[[ClientWriter, CommandT], ResultT | None]:

        def roomed_wrapper(writer: ClientWriter, command: CommandT) -> ResultT | None:
            if command.room not in set:
                return
            return callback(writer, command)

        roomed_wrapper.__name__ = callback.__name__
        roomed_wrapper.__doc__ = callback.__doc__

        return roomed_wrapper

    return roomed_decorator
