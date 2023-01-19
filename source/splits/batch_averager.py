from __future__ import annotations

import asyncio
from asyncio import Queue, TimeoutError
from collections.abc import AsyncIterator, Callable, Coroutine, Iterable
from re import Pattern
from typing import NamedTuple

from twitchio import Channel, Message
from twitchio.ext.commands import Bot

from .split import Split

__all__ = ["PartialAverage", "BatchAveragerResult", "BatchAverager"]


class PartialAverage(NamedTuple):
    """A container wrapping a floating point summand value and count, for use
    in a fold-like algorithm
    """

    value: float
    count: int = 1

    def compound(self, other: PartialAverage) -> PartialAverage:
        """Return a new partial average of the sum between values and counts"""
        return PartialAverage(
            value=self.value + other.value,
            count=self.count + other.count,
        )

    def complete(self) -> float:
        """Return the completed average"""
        return self.value / self.count


class BatchAveragerResult:
    """Yield type emitted by `BatchAverager.event_ready()`

    A simple class that wraps a reference to the averager, and the partial
    result that was calculated for a discovered batch.
    """

    __slots__ = ("_averager", "_partial")

    def __init__(self, averager: BatchAverager, partial: PartialAverage) -> None:
        self._averager = averager
        self._partial  = partial

    @property
    def averager(self) -> BatchAverager:
        """A reference to the averager instance"""
        return self._averager

    @property
    def partial(self) -> PartialAverage:
        """The partial average calculated during a discovered batch"""
        return self._partial


class BatchAverager(Split[BatchAveragerResult]):
    """A type of `Split` that finds and calculates the average value of
    discovered "batches" of floating point numbers

    A "batch" is considered to be a high-density collection of items
    discoverable within a time limit between subsequent items. A batch begins
    when the first item is discovered, and ends when no further items can be
    found within the time limit.
    """

    __slots__ = ("_pattern", "_timeout", "_density", "_results")

    def __init__(
        self,
        bot: Bot,
        *,
        channel: Channel | str,
        pattern: Pattern[str],
        timeout: float = 8.5,
        density: int = 50,
        callbacks: Iterable[Callable[[BatchAveragerResult], Coroutine]] = (),
    ) -> None:
        super().__init__(bot, channel=channel, callbacks=callbacks)
        self._pattern = pattern
        self._timeout = timeout
        self._density = density
        self._results = Queue[PartialAverage]()

    @property
    def pattern(self) -> Pattern[str]:
        return self._pattern

    @property
    def timeout(self) -> float:
        return self._timeout

    @property
    def density(self) -> int:
        return self._density

    async def event_ready(self) -> AsyncIterator[BatchAveragerResult]:
        while True:
            prev_result = await self._results.get()
            while True:
                self._results.task_done()
                try:
                    next_result = await asyncio.wait_for(self._results.get(), timeout=self.timeout)
                except TimeoutError:
                    break
                else:
                    prev_result = prev_result.compound(next_result)
            if prev_result.count < self.density:
                continue
            yield BatchAveragerResult(self, prev_result)

    async def event_message(self, message: Message) -> None:
        if message.echo:
            return
        match = self.pattern.search(message.content)
        if match is None:
            return
        self._results.put_nowait(PartialAverage(float(match.group(1))))
