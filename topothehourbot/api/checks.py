from __future__ import annotations

__all__ = ["walled", "roomed"]

from collections.abc import Callable, Coroutine
from typing import Any

from ircv3.twitch import ServerJoin, ServerMessage, ServerPart

from .client import ClientWriter
from .utilities import Callback

type RoomedCommand = ServerMessage | ServerJoin | ServerPart


def walled[ResultT]() -> Callable[[Callback[[ClientWriter, ServerMessage], ResultT]], Callback[[ClientWriter, ServerMessage], ResultT]]:

    def walled_decorator(callback: Callback[[ClientWriter, ServerMessage], ResultT]) -> Callback[[ClientWriter, ServerMessage], ResultT]:

        def walled_wrapper(writer: ClientWriter, command: ServerMessage) -> Coroutine[Any, Any, ResultT] | None:
            if writer.client.name == command.sender.name:
                return
            return callback(writer, command)

        walled_wrapper.__name__ = callback.__name__
        walled_wrapper.__doc__ = callback.__doc__

        return walled_wrapper

    return walled_decorator


def roomed[CommandT: RoomedCommand, ResultT](*rooms: str) -> Callable[[Callback[[ClientWriter, CommandT], ResultT]], Callback[[ClientWriter, CommandT], ResultT]]:
    set = frozenset(rooms)

    def roomed_decorator(callback: Callback[[ClientWriter, CommandT], ResultT]) -> Callback[[ClientWriter, CommandT], ResultT]:

        def roomed_wrapper(writer: ClientWriter, command: CommandT) -> Coroutine[Any, Any, ResultT] | None:
            if command.room not in set:
                return
            return callback(writer, command)

        roomed_wrapper.__name__ = callback.__name__
        roomed_wrapper.__doc__ = callback.__doc__

        return roomed_wrapper

    return roomed_decorator
