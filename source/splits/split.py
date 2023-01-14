from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Coroutine
from typing import Generic, TypeVar, Optional

from twitchio import Channel, Message
from twitchio.ext.commands import Bot, Cog

__all__ = ["Payload", "Split"]

T_co = TypeVar("T_co", covariant=True)


class Payload(Generic[T_co]):

    __slots__ = ("_split", "_data")

    def __init__(self, split: Split, data: T_co) -> None:
        self._split = split
        self._data = data

    @property
    def split(self) -> Split:
        return self._split

    @property
    def data(self) -> T_co:
        return self._data


class Split(Cog, Generic[T_co]):

    __slots__ = ("_bot", "_channel", "_callbacks")

    def __init__(self, bot: Bot, channel: str, *, callbacks: tuple[Callable[[Payload[T_co]], Coroutine], ...] = ()) -> None:
        self._bot       = bot
        self._channel   = channel
        self._callbacks = callbacks

    @property
    def bot(self) -> Bot:
        return self._bot

    @property
    def channel(self) -> Optional[Channel]:
        return self.bot.get_channel(self._channel)

    @property
    def callbacks(self) -> tuple[Callable[[Payload[T_co]], Coroutine], ...]:
        return self._callbacks

    async def event_ready(self) -> AsyncIterator[Payload[T_co]]:
        return
        yield

    @Cog.event("event_ready")
    async def __event_ready(self):
        async for payload in self.event_ready():
            for callback in self.callbacks:
                self.bot.loop.create_task(callback(payload))

    async def event_message(self, message: Message):
        return

    @Cog.event("event_message")
    async def __event_message(self, message: Message):
        channel = self.channel
        if channel is None or channel != message.channel:
            return
        return await self.event_message(message)
