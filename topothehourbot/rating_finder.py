from __future__ import annotations

__all__ = [
    "RatingJSON",
    "Rating",
    "RatingBatchJSON",
    "RatingBatch",
    "RatingFinder",
]

import re
from collections.abc import ValuesView
from decimal import Decimal
from typing import Self, TypedDict, override

from ircv3 import CommandProtocolJSON
from ircv3.dialects.twitch import ServerMessage, ServerPart

from .api.client import (ChannelWriter, SupportsOnChannelMessage,
                         SupportsOnChannelPart)
from .api.utilities import Buffer, Failure, Job, Signal, Success


class RatingJSON(TypedDict):

    message: CommandProtocolJSON
    value: float
    index_begin: int
    index_end: int


class Rating:

    __slots__ = ("message", "value", "index_begin", "index_end")
    message: ServerMessage
    value: Decimal
    index_begin: int
    index_end: int

    def __init__(
        self,
        message: ServerMessage,
        value: Decimal,
        index_begin: int,
        index_end: int,
    ) -> None:
        self.message = message
        self.value = value
        self.index_begin = index_begin
        self.index_end = index_end

    @property
    def key(self) -> str:
        """The rating key

        Useful for identifying ratings sourced from the same user. This value
        is the same as ``message.sender.id``.
        """
        return self.message.sender.id

    def to_json(self) -> RatingJSON:
        """Return a JSON representation of the rating"""
        return {
            "message": self.message.to_json(),
            "value": float(self.value),
            "index_begin": self.index_begin,
            "index_end": self.index_end,
        }


class RatingBatchJSON(TypedDict):

    ratings: list[RatingJSON]
    count: int
    sum: float
    mean: float | None


class RatingBatch:

    __slots__ = ("_map", "_sum")
    _map: dict[str, Rating]
    """The rating map

    A mapping of rating "keys" to their respective ``Rating`` objects. The
    users' Twitch IDs are used as the keys, thus allowing only one rating per
    user. When a rating is added, it overwrites any prior that existed.
    """
    _sum: Decimal
    """The rating sum

    Useful for many calculations. This value is updated for each addition to
    the map.
    """

    def __init__(self) -> None:
        self._map = {}
        self._sum = Decimal()

    @property
    def ratings(self) -> ValuesView[Rating]:
        """A view on the batch's current collection of ratings"""
        return self._map.values()

    @property
    def count(self) -> int:
        """The number of ratings"""
        return len(self._map)

    @property
    def sum(self) -> Decimal:
        """The rating sum"""
        return self._sum

    @property
    def mean(self) -> Decimal | None:
        """The rating mean

        ``None`` if the map is empty.
        """
        count = self.count
        if count:
            return self.sum / count

    def add(self, rating: Rating) -> Self:
        """Add a rating to the batch"""
        key = rating.key
        map = self._map
        sum = self._sum
        if key in map:
            sum -= map[key].value
        self._sum = sum + rating.value
        map[key] = rating
        return self

    def to_json(self) -> RatingBatchJSON:
        """Return a JSON representation of the batch"""
        return {
            "ratings": [rating.to_json() for rating in self.ratings],
            "count": self.count,
            "sum": float(self.sum),
            "mean": None if self.mean is None else float(self.mean),
        }


class RatingFinder(
    SupportsOnChannelMessage,
    SupportsOnChannelPart,
):

    pattern = re.compile(
        pattern=r"""
        (?:^|\s)                   # Should proceed the beginning or whitespace
        (
            [-+]?                  # Optional + or -
            (?:
                (?:\d+(?:\.\d*)?)  # Integer with optional decimal part
                |
                (?:\.\d+)          # Decimal part only
            )
        )
        \s?/\s?10                  # Denominator of 10
        (?:$|[\s,.!?])             # Should precede the end, whitespace, or some punctuation
        """,
        flags=re.VERBOSE,
    )

    __slots__ = (
        "_job",
        "delay",
        "max_count",
        "min_count",
    )
    _job: Job[[ChannelWriter, Rating], RatingBatch, RatingBatch]
    delay: float
    max_count: int | None
    min_count: int

    def __init__(
        self,
        *,
        delay: float = 8.5,
        max_count: int | None = None,
        min_count: int = 40,
    ) -> None:
        super().__init__()
        self._job = Job(self._job_process)
        self.delay = delay
        self.max_count = max_count
        self.min_count = min_count

    @property
    def success_signal(self) -> Signal[[RatingBatch, ChannelWriter, Rating], object]:
        return self._job.success_signal

    @property
    def failure_signal(self) -> Signal[[RatingBatch, ChannelWriter, Rating], object]:
        return self._job.failure_signal

    def find(self, message: ServerMessage) -> Rating | None:
        match = self.pattern.search(message.comment)
        if match is not None:
            return Rating(
                message=message,
                value=Decimal(match.group(1)),
                index_begin=match.span(1)[0],
                index_end=match.span(1)[1],
            )

    async def _job_process(self, writer: ChannelWriter, initial_rating: Rating) -> Success[RatingBatch] | Failure[RatingBatch]:
        ratings = Buffer[Rating]()
        ratings.send(initial_rating)

        async def on_channel_message(writer: ChannelWriter, message: ServerMessage) -> None:
            if writer.client.name == message.sender.name:
                return
            rating = self.find(message)
            if rating is None:
                return
            ratings.send(rating)

        with (
            writer
                .channel
                .message_signal
                .continuation(on_channel_message)
        ):
            batch = await (
                aiter(ratings)
                    .finite_timeout(self.delay)
                    .limit(self.max_count)
                    .reduce(RatingBatch(), RatingBatch.add)
            )
            if batch.count < self.min_count:
                result = Failure(batch)
            else:
                result = Success(batch)

        return result

    @override
    async def on_channel_message(self, writer: ChannelWriter, command: ServerMessage) -> None:
        if writer.client.name == command.sender.name:
            return
        rating = self.find(command)
        if rating is None:
            return
        with (
            writer
                .channel
                .message_signal
                .suspension(self.on_channel_message)
        ):
            await self._job.run(writer, rating)

    @override
    async def on_channel_part(self, writer: ChannelWriter, command: ServerPart) -> None:
        if command.source.startswith(writer.client.name):
            for processor in (
                self._job,
                self._job.success_signal,
                self._job.failure_signal,
            ):
                processor.cancel()
            writer.channel.remove_callbacks(self)
