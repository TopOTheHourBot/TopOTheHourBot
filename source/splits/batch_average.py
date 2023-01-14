from __future__ import annotations

import asyncio
import re
from asyncio import Queue, TimeoutError
from collections.abc import AsyncIterator, Callable, Coroutine
from re import Pattern
from typing import NamedTuple

from twitchio import Message
from twitchio.ext.commands import Bot

from .split import Payload, Split

__all__ = ["BatchAverageSplit", "PartialAverage"]


class PartialAverage(NamedTuple):

    value: float
    count: int = 1

    def compound(self, other: PartialAverage) -> PartialAverage:
        return PartialAverage(
            value=self.value + other.value,
            count=self.count + other.count,
        )

    def complete(self) -> float:
        return self.value / self.count


class BatchAverageSplit(Split[PartialAverage]):

    __slots__ = ("_pattern", "_timeout", "_density", "_scores")

    def __init__(
        self,
        bot: Bot,
        channel: str,
        *,
        callbacks: tuple[Callable[[Payload[PartialAverage]], Coroutine], ...] = (),
        pattern: Pattern[str] = re.compile(r"(-?\d+(?:\.\d*)?)\s?/\s?10"),
        timeout: float = 8.5,
        density: int = 50,
    ) -> None:
        super().__init__(bot, channel, callbacks=callbacks)
        self._pattern = pattern
        self._timeout = timeout
        self._density = density
        self._scores  = Queue[PartialAverage]()

    @property
    def pattern(self) -> Pattern[str]:
        return self._pattern

    @property
    def timeout(self) -> float:
        return self._timeout

    @property
    def density(self) -> int:
        return self._density

    async def event_ready(self) -> AsyncIterator[Payload[PartialAverage]]:
        while True:
            prev_score = await self._scores.get()
            while True:
                self._scores.task_done()
                try:
                    next_score = await asyncio.wait_for(self._scores.get(), timeout=self.timeout)
                except TimeoutError:
                    break
                else:
                    prev_score = prev_score.compound(next_score)
            if prev_score.count < self.density:
                continue
            yield Payload(self, prev_score)

    async def event_message(self, message: Message) -> None:
        if message.echo:
            return
        match = self.pattern.search(message.content)
        if match is None:
            return
        score = PartialAverage(
            clamp(
                float(match.group(1)),
                lower=00.0,
                upper=10.0,
            ),
        )
        self._scores.put_nowait(score)


def clamp(x: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, x))
