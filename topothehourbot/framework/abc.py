from __future__ import annotations

__all__ = [
    "ensure_series",
    "EventResult",
    "EventProtocol",
    "EventBroadcaster",
]

from abc import ABCMeta, abstractmethod
from asyncio import TaskGroup
from collections.abc import AsyncIterator, Coroutine, Iterable, Iterator
from typing import Any, Optional, Self, override

from ircv3 import IRCv3ClientCommandProtocol
from ircv3.dialects.twitch import (RoomState, ServerJoin, ServerPart,
                                   ServerPrivateMessage)

from .series import Series, series

type EventResult = (
    Coroutine[Any, Any, Optional[IRCv3ClientCommandProtocol]]
    | Series[IRCv3ClientCommandProtocol]
)


def ensure_series(result: EventResult, /) -> Series[IRCv3ClientCommandProtocol]:
    """Return ``result`` as a guaranteed ``Series`` object

    Utility function for handling ``EventResult`` types in particular.
    Instances of ``Coroutine[Any, Any, Optional[IRCv3ClientCommandProtocol]]``
    are converted to a zero-or-one length ``Series``, where if the coroutine
    returns ``None``, the series ends, otherwise the series yields.
    """
    if type(result) is Series:  # Series is final
        return result

    @series
    async def one_or_none[T](coro: Coroutine[Any, Any, Optional[T]], /) -> AsyncIterator[T]:
        value = await coro
        if value is None:
            return
        yield value

    return one_or_none(result)


class EventProtocol(metaclass=ABCMeta):

    __slots__ = ()

    @abstractmethod
    def on_connect(self) -> EventResult:
        """Event handler called when the client first connects to the Twitch
        IRC server
        """
        raise NotImplementedError

    @abstractmethod
    def on_join(self, join: ServerJoin) -> EventResult:
        """Event handler called when the client receives a JOIN from the Twitch
        IRC server
        """
        raise NotImplementedError

    @abstractmethod
    def on_part(self, part: ServerPart) -> EventResult:
        """Event handler called when the client receives a PART from the Twitch
        IRC server
        """
        raise NotImplementedError

    @abstractmethod
    def on_message(self, message: ServerPrivateMessage) -> EventResult:
        """Event handler called when the client receives a PRIVMSG from the
        Twitch IRC server
        """
        raise NotImplementedError

    @abstractmethod
    def on_room_state(self, room_state: RoomState) -> EventResult:
        """Event handler called when the client receives a ROOMSTATE from the
        Twitch IRC server
        """
        raise NotImplementedError


class EventBroadcaster(EventProtocol, metaclass=ABCMeta):

    __slots__ = ("_listeners")
    _listeners: set[EventProtocol]

    def __init__(self, *, listeners: Iterable[EventProtocol] = ()) -> None:
        self._listeners = set(listeners)

    def listeners(self) -> Iterator[EventProtocol]:
        """Return an iterator over the currently-enrolled listeners"""
        return iter(self._listeners)

    def enroll_listener(self, listener: EventProtocol, /) -> Self:
        """Enroll a listener and return the broadcaster

        The listener object must be hashable.
        """
        self._listeners.add(listener)
        return self

    def unenroll_listener(self, listener: EventProtocol, /) -> Self:
        """Unenroll a listener and return the broadcaster"""
        self._listeners.discard(listener)
        return self

    @abstractmethod
    async def event_callback(self, command: IRCv3ClientCommandProtocol) -> None:
        """Return a callback function used when a listener's event handler
        emits a client command in response
        """
        raise NotImplementedError

    @override
    async def on_connect(self) -> None:
        listeners = self.listeners()
        listener = next(listeners, None)
        if listener is None:
            return
        async with TaskGroup() as tasks:
            calls = (
                ensure_series(listener.on_connect())
                for listener in listeners
            )
            async for command in (
                ensure_series(listener.on_connect())
                    .merge(*calls)
            ):
                tasks.create_task(self.event_callback(command))

    @override
    async def on_join(self, join: ServerJoin) -> None:
        listeners = self.listeners()
        listener = next(listeners, None)
        if listener is None:
            return
        async with TaskGroup() as tasks:
            calls = (
                ensure_series(listener.on_join(join))
                for listener in listeners
            )
            async for command in (
                ensure_series(listener.on_join(join))
                    .merge(*calls)
            ):
                tasks.create_task(self.event_callback(command))

    @override
    async def on_part(self, part: ServerPart) -> None:
        listeners = self.listeners()
        listener = next(listeners, None)
        if listener is None:
            return
        async with TaskGroup() as tasks:
            calls = (
                ensure_series(listener.on_part(part))
                for listener in listeners
            )
            async for command in (
                ensure_series(listener.on_part(part))
                    .merge(*calls)
            ):
                tasks.create_task(self.event_callback(command))

    @override
    async def on_message(self, message: ServerPrivateMessage) -> None:
        listeners = self.listeners()
        listener = next(listeners, None)
        if listener is None:
            return
        async with TaskGroup() as tasks:
            calls = (
                ensure_series(listener.on_message(message))
                for listener in listeners
            )
            async for command in (
                ensure_series(listener.on_message(message))
                    .merge(*calls)
            ):
                tasks.create_task(self.event_callback(command))

    @override
    async def on_room_state(self, room_state: RoomState) -> None:
        listeners = self.listeners()
        listener = next(listeners, None)
        if listener is None:
            return
        async with TaskGroup() as tasks:
            calls = (
                ensure_series(listener.on_room_state(room_state))
                for listener in listeners
            )
            async for command in (
                ensure_series(listener.on_room_state(room_state))
                    .merge(*calls)
            ):
                tasks.create_task(self.event_callback(command))
