from __future__ import annotations

import asyncio
import re
from asyncio import Queue, TimeoutError
from collections.abc import AsyncIterator, Callable, Coroutine, Iterable
from typing import NamedTuple

from twitchio import Channel, Message
from twitchio.ext.commands import Bot

from .split import Split

__all__ = ["RatingAveragerResult", "RatingAverager"]


class RatingAveragerResult(NamedTuple):
    """Yield type emitted by `RatingAverager.event_ready()`

    A simple container wrapping a reference to the channel, the number of
    participating chatters, and the rating.
    """

    channel: Channel
    density: int
    rating: float


class RatingAverager(Split[RatingAveragerResult]):
    """A type of `Split` that finds and calculates the average value of
    discovered "batches" of ratings; values that look vaguely like "X/10",
    where "X" is a number between 0 and 10.

    We consider a "batch" to be a high-density collection of items discoverable
    within a time limit between those items. A batch begins when the first item
    is discovered, and ends when the time limit is left to decay.
    """

    PATTERN = re.compile(
        r"""
        (?:^|\s)            # should proceed the beginning or whitespace
        (
            (?:(?:\d|10)\.?)  # any integer within range 0 to 10
            |
            (?:\d?\.\d+)      # any decimal within range 0 to 9
        )
        \s?/\s?10           # denominator of 10
        (?:$|[\s,.!?])      # should precede the end, whitespace, or some punctuation
        """,
        flags=re.ASCII | re.VERBOSE,
    )

    __slots__ = ("_timeout", "_min_density", "_max_density", "_ratings")

    def __init__(
        self,
        bot: Bot,
        *,
        channel: Channel | str,
        callbacks: Iterable[Callable[[RatingAveragerResult], Coroutine]] = (),
        timeout: float = 8.5,
        min_density: int = 100,
        max_density: int = 2 ** 16,
    ) -> None:
        super().__init__(bot, channel=channel, callbacks=callbacks)

        self._timeout = timeout
        self._min_density = min_density
        self._max_density = max_density

        self._ratings = Queue[float]()

    @property
    def timeout(self) -> float:
        return self._timeout

    @property
    def min_density(self) -> int:
        return self._min_density

    @property
    def max_density(self) -> int:
        return self._max_density

    def put(self, rating: float) -> None:
        self._ratings.put_nowait(rating)

    async def get(self) -> float:
        return await self._ratings.get()

    def done(self) -> None:
        self._ratings.task_done()

    async def event_ready(self) -> AsyncIterator[RatingAveragerResult]:
        while True:
            rating = await self.get()
            for density in range(1, self.max_density + 1):
                self.done()
                try:
                    next_rating = await asyncio.wait_for(self.get(), timeout=self.timeout)
                except TimeoutError:
                    break
                else:
                    rating += next_rating
            if density < self.min_density:
                continue
            yield RatingAveragerResult(self.channel, density=density, rating=rating)

    async def event_message(self, message: Message) -> None:
        if message.echo:
            return
        match = self.PATTERN.search(message.content)
        if match is None:
            return
        self.put(float(match.group(1)))
