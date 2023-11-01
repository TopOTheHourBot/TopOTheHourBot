from __future__ import annotations

__all__ = [
    "EventListener",
    "EventBroadcaster",
    "EventRebroadcaster",
]

from abc import ABCMeta, abstractmethod
from asyncio import TaskGroup
from collections.abc import Coroutine, Iterable, Iterator
from typing import Any, Optional, Protocol, Self

from ircv3 import IRCv3ClientCommandProtocol
from ircv3.dialects.twitch import (RoomState, ServerJoin, ServerPart,
                                   ServerPrivateMessage)

from .series import Series


class EventListener(Protocol):

    @abstractmethod
    def on_connect(self) -> Series[IRCv3ClientCommandProtocol]:
        """Event handler called when the client first connects to the Twitch
        IRC server
        """
        raise NotImplementedError

    @abstractmethod
    def on_join(self, command: ServerJoin, /) -> Series[IRCv3ClientCommandProtocol]:
        """Event handler called when the client receives a JOIN from the Twitch
        IRC server
        """
        raise NotImplementedError

    @abstractmethod
    def on_part(self, command: ServerPart, /) -> Series[IRCv3ClientCommandProtocol]:
        """Event handler called when the client receives a PART from the Twitch
        IRC server
        """
        raise NotImplementedError

    @abstractmethod
    def on_message(self, command: ServerPrivateMessage, /) -> Series[IRCv3ClientCommandProtocol]:
        """Event handler called when the client receives a PRIVMSG from the
        Twitch IRC server
        """
        raise NotImplementedError

    @abstractmethod
    def on_room_state(self, command: RoomState, /) -> Series[IRCv3ClientCommandProtocol]:
        """Event handler called when the client receives a ROOMSTATE from the
        Twitch IRC server
        """
        raise NotImplementedError


class EventBroadcaster(metaclass=ABCMeta):

    __slots__ = ("_listeners")
    _listeners: set[EventListener]

    def __init__(self, *, listeners: Iterable[EventListener] = ()) -> None:
        self._listeners = set(listeners)

    def listeners(self) -> Iterator[EventListener]:
        """Return an iterator over the currently-enrolled listeners"""
        return iter(self._listeners)

    def enroll_listener(self, listener: EventListener, /) -> Self:
        """Enroll a listener and return the broadcaster

        The listener object must be hashable.
        """
        self._listeners.add(listener)
        return self

    def unenroll_listener(self, listener: EventListener, /) -> Self:
        """Unenroll a listener and return the broadcaster"""
        self._listeners.discard(listener)
        return self

    @abstractmethod
    async def event_callback(self, command: IRCv3ClientCommandProtocol, /) -> None:
        """Callback function used when a listener's event handler emits a
        responding client command
        """
        raise NotImplementedError

    # This class is geared towards acting as the client, and so each event
    # handler is just a coroutine that returns None, which makes it easy to
    # "fire and forget" them in something like a TaskGroup.

    # The type-hinting is broad to allow sub-classes the ability to inherit the
    # broadcasting functionality, while also yielding its own commands via the
    # Series.from_coroutine() decorator.

    async def on_connect(self) -> Optional[IRCv3ClientCommandProtocol]:
        listeners = self.listeners()
        listener = next(listeners, None)
        if listener is None:
            return
        async with TaskGroup() as tasks:
            calls = (
                listener.on_connect()
                for listener in listeners
            )
            async for command in (
                listener.on_connect()
                    .merge(*calls)
            ):
                tasks.create_task(self.event_callback(command))

    async def on_join(self, command: ServerJoin, /) -> Optional[IRCv3ClientCommandProtocol]:
        listeners = self.listeners()
        listener = next(listeners, None)
        if listener is None:
            return
        async with TaskGroup() as tasks:
            calls = (
                listener.on_join(command)
                for listener in listeners
            )
            async for feedback in (
                listener.on_join(command)
                    .merge(*calls)
            ):
                tasks.create_task(self.event_callback(feedback))

    async def on_part(self, command: ServerPart, /) -> Optional[IRCv3ClientCommandProtocol]:
        listeners = self.listeners()
        listener = next(listeners, None)
        if listener is None:
            return
        async with TaskGroup() as tasks:
            calls = (
                listener.on_part(command)
                for listener in listeners
            )
            async for feedback in (
                listener.on_part(command)
                    .merge(*calls)
            ):
                tasks.create_task(self.event_callback(feedback))

    async def on_message(self, command: ServerPrivateMessage, /) -> Optional[IRCv3ClientCommandProtocol]:
        listeners = self.listeners()
        listener = next(listeners, None)
        if listener is None:
            return
        async with TaskGroup() as tasks:
            calls = (
                listener.on_message(command)
                for listener in listeners
            )
            async for feedback in (
                listener.on_message(command)
                    .merge(*calls)
            ):
                tasks.create_task(self.event_callback(feedback))

    async def on_room_state(self, command: RoomState, /) -> Optional[IRCv3ClientCommandProtocol]:
        listeners = self.listeners()
        listener = next(listeners, None)
        if listener is None:
            return
        async with TaskGroup() as tasks:
            calls = (
                listener.on_room_state(command)
                for listener in listeners
            )
            async for feedback in (
                listener.on_room_state(command)
                    .merge(*calls)
            ):
                tasks.create_task(self.event_callback(feedback))


class EventRebroadcaster(EventBroadcaster, metaclass=ABCMeta):

    __slots__ = ()

    @Series.from_coroutine
    def on_connect(self) -> Coroutine[Any, Any, Optional[IRCv3ClientCommandProtocol]]:
        return super().on_connect()

    @Series.from_coroutine
    def on_join(self, command: ServerJoin, /) -> Coroutine[Any, Any, Optional[IRCv3ClientCommandProtocol]]:
        return super().on_join(command)

    @Series.from_coroutine
    def on_part(self, command: ServerPart, /) -> Coroutine[Any, Any, Optional[IRCv3ClientCommandProtocol]]:
        return super().on_part(command)

    @Series.from_coroutine
    def on_message(self, command: ServerPrivateMessage, /) -> Coroutine[Any, Any, Optional[IRCv3ClientCommandProtocol]]:
        return super().on_message(command)

    @Series.from_coroutine
    def on_room_state(self, command: RoomState, /) -> Coroutine[Any, Any, Optional[IRCv3ClientCommandProtocol]]:
        return super().on_room_state(command)
