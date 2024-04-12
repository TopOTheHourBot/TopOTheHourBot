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
from ircv3.twitch import ServerMessage

from .api.client import ChannelWriter, SupportsOnChannelMessage
from .api.utilities import Buffer, Job, Signal


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
    size: int
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
    def size(self) -> int:
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
        size = self.size
        if size:
            return self.sum / size

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
            "size": self.size,
            "sum": float(self.sum),
            "mean": None if self.mean is None else float(self.mean),
        }


class RatingFinder(SupportsOnChannelMessage):

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
        "batch_signal",
        "delay",
        "min_size",
        "max_size",
    )
    _job: Job[[ChannelWriter, Rating], None]
    batch_signal: Signal[[ChannelWriter, RatingBatch], object]
    delay: float
    min_size: int
    max_size: int | None

    def __init__(
        self,
        *,
        delay: float = 8.5,
        min_size: int = 40,
        max_size: int | None = None,
    ) -> None:
        self._job = Job(self._job_process)
        self.batch_signal = Signal()
        self.delay = delay
        self.min_size = min_size
        self.max_size = max_size

    async def _job_process(self, writer: ChannelWriter, initial_rating: Rating) -> None:
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
                .add_callback(on_channel_message, temporary=True)
        ):
            batch = await (
                aiter(ratings)
                    .finite_timeout(self.delay)
                    .limit(self.max_size)
                    .reduce(RatingBatch(), RatingBatch.add)
            )

        if batch.size >= self.min_size:
            self.batch_signal.maybe_run(writer, batch)

    def find(self, message: ServerMessage) -> Rating | None:
        match = self.pattern.search(message.comment)
        if match is not None:
            return Rating(
                message=message,
                value=Decimal(match.group(1)),
                index_begin=match.span(1)[0],
                index_end=match.span(1)[1],
            )

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
                .remove_callback(self.on_channel_message, temporary=True)
        ):
            await self._job.run(writer, rating)
