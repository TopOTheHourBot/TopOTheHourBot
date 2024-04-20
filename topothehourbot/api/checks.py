from __future__ import annotations

__all__ = ["walled", "roomed"]

from collections.abc import Callable

from ircv3.twitch import (Notice, ServerJoin, ServerMessage, ServerPart,
                          UserState)

from .client import Client
from .utilities import CallbackReturn

type RoomedCommand = ServerMessage | ServerJoin | ServerPart | UserState | Notice


def walled[
    CallbackReturnT: CallbackReturn,
]() -> Callable[[Callable[[Client, ServerMessage], CallbackReturnT]], Callable[[Client, ServerMessage], CallbackReturnT | None]]:
    """Return a decorator that discards echoed messages

    Note that this function is specific to ``PRIVMSG`` (``ServerMessage``)
    handlers, as other commands are not echoed by the Twitch server.
    """

    def walled_decorator(callback: Callable[[Client, ServerMessage], CallbackReturnT]) -> Callable[[Client, ServerMessage], CallbackReturnT | None]:

        def walled_wrapper(client: Client, command: ServerMessage) -> CallbackReturnT | None:
            if client.name == command.sender.name:
                return
            return callback(client, command)

        walled_wrapper.__name__ = callback.__name__
        walled_wrapper.__doc__ = callback.__doc__

        return walled_wrapper

    return walled_decorator


def roomed[
    RoomedCommandT: RoomedCommand,
    CallbackReturnT: CallbackReturn,
](*rooms: str) -> Callable[[Callable[[Client, RoomedCommandT], CallbackReturnT]], Callable[[Client, RoomedCommandT], CallbackReturnT | None]]:
    """Return a decorator that discards messages from rooms not found within
    the given list

    Handler must be for a "roomed command", i.e., a server command whose first
    argument is the room for which it applies in. The parser currently supports
    the following roomed commands from the Twitch IRC dialect:
    - ``PRIVMSG`` (``ServerMessage``)
    - ``JOIN`` (``ServerJoin``)
    - ``PART`` (``ServerPart``)
    - ``ROOMSTATE`` (``RoomState``)
    - ``USERSTATE`` (``UserState``)
    - ``NOTICE`` (``Notice``)
    """
    set = frozenset(rooms)

    def roomed_decorator(callback: Callable[[Client, RoomedCommandT], CallbackReturnT]) -> Callable[[Client, RoomedCommandT], CallbackReturnT | None]:

        def roomed_wrapper(client: Client, command: RoomedCommandT) -> CallbackReturnT | None:
            if command.room not in set:
                return
            return callback(client, command)

        roomed_wrapper.__name__ = callback.__name__
        roomed_wrapper.__doc__ = callback.__doc__

        return roomed_wrapper

    return roomed_decorator
