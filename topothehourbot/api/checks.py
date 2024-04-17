from __future__ import annotations

__all__ = ["walled", "roomed"]

from collections.abc import Callable, Coroutine
from typing import Any

from ircv3.twitch import ServerJoin, ServerMessage, ServerPart, UserState

from .client import Client

type RoomedCommand = ServerMessage | ServerJoin | ServerPart | UserState


def walled[
    ResultT: Coroutine[Any, Any, object] | None,
]() -> Callable[[Callable[[Client, ServerMessage], ResultT]], Callable[[Client, ServerMessage], ResultT | None]]:

    def walled_decorator(callback: Callable[[Client, ServerMessage], ResultT]) -> Callable[[Client, ServerMessage], ResultT | None]:

        def walled_wrapper(client: Client, command: ServerMessage) -> ResultT | None:
            if client.name == command.sender.name:
                return
            return callback(client, command)

        walled_wrapper.__name__ = callback.__name__
        walled_wrapper.__doc__ = callback.__doc__

        return walled_wrapper

    return walled_decorator


def roomed[
    RoomedCommandT: RoomedCommand,
    ResultT: Coroutine[Any, Any, object] | None,
](*rooms: str) -> Callable[[Callable[[Client, RoomedCommandT], ResultT]], Callable[[Client, RoomedCommandT], ResultT | None]]:
    set = frozenset(rooms)

    def roomed_decorator(callback: Callable[[Client, RoomedCommandT], ResultT]) -> Callable[[Client, RoomedCommandT], ResultT | None]:

        def roomed_wrapper(client: Client, command: RoomedCommandT) -> ResultT | None:
            if command.room not in set:
                return
            return callback(client, command)

        roomed_wrapper.__name__ = callback.__name__
        roomed_wrapper.__doc__ = callback.__doc__

        return roomed_wrapper

    return roomed_decorator
