from collections.abc import AsyncIterator, Callable, Coroutine
from typing import Generic, Optional, TypeVar

from twitchio import Channel, Message
from twitchio.ext.commands import Bot, Cog

__all__ = ["Split"]

T_co = TypeVar("T_co", covariant=True)


class Split(Cog, Generic[T_co]):
    """A type of `Cog` that "splits" event handlers by a given, singular
    channel, with better support for background polling

    The `event_ready()` method is expected to be an async generator (or a
    method that returns an async iterator). Its yielded values are
    asynchronously passed to callbacks that can be specified at construction
    time.
    """

    __slots__ = ("_bot", "_channel", "_callbacks")

    def __init__(
        self,
        bot: Bot,
        *,
        channel: str,
        callbacks: tuple[Callable[[T_co], Coroutine], ...] = (),
    ) -> None:
        self._bot       = bot
        self._channel   = channel
        self._callbacks = callbacks

    @property
    def bot(self) -> Bot:
        """The bot associated with the split"""
        return self._bot

    @property
    def channel(self) -> Optional[Channel]:
        """The channel that's filtered for by the split

        If the bot is not connected to the channel specified at construction
        time, this property will be `None`.
        """
        return self.bot.get_channel(self._channel)

    @property
    def callbacks(self) -> tuple[Callable[[T_co], Coroutine], ...]:
        """A tuple of async callbacks dispatched when results are yielded by
        `event_ready()`
        """
        return self._callbacks

    async def event_ready(self) -> AsyncIterator[T_co]:
        """Event called when the bot has logged in and is ready

        Expected to take the form of an async iterator. If the implementation
        has no results to yield, using the idiom:

        ```
        return
        yield
        ```

        is a quick and easy way to kill the callback dispatcher (this is also
        the default implementation).
        """
        return
        yield

    @Cog.event("event_ready")
    async def __event_ready(self):
        async for result in self.event_ready():
            for callback in self.callbacks:
                self.bot.loop.create_task(callback(result))

    async def event_message(self, message: Message):
        """Event called when a PRIVMSG is received"""
        return

    @Cog.event("event_message")
    async def __event_message(self, message: Message):
        channel = self.channel
        if channel is None:
            return
        if channel != message.channel:
            return
        return await self.event_message(message)
