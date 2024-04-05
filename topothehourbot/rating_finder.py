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
from typing import TypedDict, override

from ircv3 import CommandProtocolJSON
from ircv3.dialects.twitch import ServerMessage

from .api.app import ChannelApp, Plugin
from .api.client import Channel
from .api.utilities import Buffer, BufferedJob, Failure, Signal, Success


class RatingJSON(TypedDict):

    message: CommandProtocolJSON
    value: float


class Rating:

    __slots__ = ("message", "value")
    message: ServerMessage
    """The message containing the rating value"""
    value: Decimal
    """The rating value"""

    def __init__(self, message: ServerMessage, value: Decimal) -> None:
        self.message = message
        self.value = value

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
        """A view on the set's current collection of ratings"""
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

    def add(self, rating: Rating) -> None:
        """Add a rating to the set"""
        key = rating.key
        map = self._map
        sum = self._sum
        if key in map:
            sum -= map[key].value
        self._sum = sum + rating.value
        map[key] = rating

    def to_json(self) -> RatingBatchJSON:
        """Return a JSON representation of the set"""
        return {
            "ratings": [rating.to_json() for rating in self.ratings],
            "count": self.count,
            "sum": float(self.sum),
            "mean": None if self.mean is None else float(self.mean),
        }


class RatingFinder(Plugin[ChannelApp]):

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
        "_channel",
        "success_signal",
        "failure_signal",
        "delay",
        "max_count",
        "min_count",
    )
    _job: BufferedJob[Rating, RatingBatch, RatingBatch]
    _channel: Channel
    success_signal: Signal[[Channel, RatingBatch], object]
    failure_signal: Signal[[Channel, RatingBatch], object]
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
        self._job = BufferedJob(self._job_process)
        self._job.success_signal.add_callback(self._on_job_success)
        self._job.failure_signal.add_callback(self._on_job_failure)
        self.success_signal = Signal()
        self.failure_signal = Signal()
        self.delay = delay
        self.max_count = max_count
        self.min_count = min_count

    async def _job_process(self, buffer: Buffer[Rating]) -> Success[RatingBatch] | Failure[RatingBatch]:
        ratings = RatingBatch()
        max_count = self.max_count
        min_count = self.min_count
        delay = self.delay
        async for rating in (
            aiter(buffer)
                .finite_timeout(delay)
                .limit(max_count)
        ):
            ratings.add(rating)
        if ratings.count < min_count:
            return Failure(ratings)
        return Success(ratings)

    async def _on_job_success(self, ratings: RatingBatch) -> None:
        waiter = self.success_signal.maybe_run(self._channel, ratings)
        if waiter is not None:
            await waiter

    async def _on_job_failure(self, ratings: RatingBatch) -> None:
        waiter = self.failure_signal.maybe_run(self._channel, ratings)
        if waiter is not None:
            await waiter

    async def _on_channel_ready(self, channel: Channel) -> None:
        self._channel = channel

    async def _on_channel_message(self, channel: Channel, message: ServerMessage) -> None:
        rater = message.sender
        if channel.client.name == rater.name:
            return
        match = self.pattern.search(message.comment)
        if match is None:
            return
        job = self._job
        if not job.running():
            job.run()
        rating = Rating(
            message=message,
            value=Decimal(match.group(1)),
        )
        job.send(rating)

    @override
    def on_load(self, app: ChannelApp) -> ChannelApp:
        app = super().on_load(app)
        app.ready_signal.add_callback(self._on_channel_ready)
        app.message_signal.add_callback(self._on_channel_message)
        return app

    @override
    def on_unload(self, app: ChannelApp) -> ChannelApp:
        app = super().on_unload(app)
        app.ready_signal.remove_callback(self._on_channel_ready)
        app.message_signal.remove_callback(self._on_channel_message)
        return app
