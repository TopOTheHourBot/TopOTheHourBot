import asyncio
import itertools
import math
import random
import re
from asyncio import Queue, TimeoutError
from collections.abc import Coroutine
from re import Pattern
from typing import NamedTuple, Optional

from twitchio import Channel, Message
from twitchio.ext.commands import Bot, Cog

__all__ = ["RatingAggregator"]


class Payload(NamedTuple):
    """Information pertaining to a successful aggregation

    Contains the mean value, `mean`, the number of (non-unique) values used in
    the calculation of the mean, `count`, and two booleans, `max` and `min`,
    that indicate whether the mean was the best or worst of the current
    runtime.

    If both `max` and `min` are true, then the given `Payload` instance is
    guaranteed to be the first succesful aggregation result. In all other
    cases, only one of the two attributes will be true.
    """
    mean: float
    count: int
    max: bool
    min: bool


class RatingAggregator(Cog):
    """A single-channel cog that averages ad segue ratings

    This is primarily intended for use in HasanAbi's chat, but can be tuned for
    others by changing the class variables below.
    """

    CHANNEL_NAME: str     = "hasanabi"  # The canonical Twitch username of the broadcaster - must be lowercased
    CHANNEL_NICKNAME: str = "hassy"     # A nickname used in the message

    TIMEOUT: float = 9.5  # The time, in seconds, for which subsequent values must be found before a message is sent

    # The key and value patterns, and their respective densities.

    # When aggregating, a post() task will only be dispatched if the key and
    # value patterns have matched a number of times greater than their
    # respective densities. When a value match occurs, aggregate() will be
    # dispatched by event_message().

    KEY: Pattern[str] = re.compile(r"DANKIES|PogO|TomatoTime")
    VAL: Pattern[str] = re.compile(r"(-?\d+(?:\.\d*)?)\s?/\s?10")
    KEY_DENSITY: int = 3
    VAL_DENSITY: int = 20

    # Emotes used in the post() message based on how high/low the average was.

    # A positive emote is used if the average was the best of its runtime, or
    # if the average was above 5. If neither, a negative emote is used.
    # Emotes are selected at random with equal weighting.

    NEGATIVE_EMOTES: tuple[str, ...] = (
        "Sadge",
        "FeelsBadMan",
        "widepeepoSad",
        "unPOGGERS",
        "PogO",
        "😔",
        "Awkward",
        "peepoPogO",
        "hasCringe",
    )
    POSITIVE_EMOTES: tuple[str, ...] = (
        "Gladge",
        "FeelsOkayMan",
        "widepeepoHappy",
        "POGGERS",
        "PogU",
        "😳",
        "pugPls",
        "peepoPog",
        "hasSoy",
    )

    __slots__ = ("bot", "tasks", "pool", "max", "min")

    def __init__(self, bot: Bot) -> None:
        self.bot = bot

        self.tasks = {}
        self.pool  = Queue()

        self.max = -math.inf
        self.min =  math.inf

    def create_task(self, coro: Coroutine, *, name: Optional[str] = None) -> None:
        """Create a background task from `coro`, ensuring it is garbage
        collected

        This method is primarily intended for functions of `RatingAggregator`.
        """
        task = asyncio.create_task(coro, name=name)

        name = task.get_name()  # Get the task's name in case we weren't provided one
        self.tasks[name] = task

        task.add_done_callback(lambda task: self.tasks.pop(task.get_name()))

    async def aggregate(self, channel: Channel) -> None:
        """Wait for messages in `pool`, averaging their values until timeout,
        and dispatch a `post()` task when appropriate
        """
        timeout = self.TIMEOUT

        key  = self.KEY
        val  = self.VAL
        kmin = self.KEY_DENSITY
        nmin = self.VAL_DENSITY

        x = 0.0
        k = 0

        for n in itertools.count():
            try:
                message, match = await asyncio.wait_for(self.pool.get(), timeout=timeout)
            except TimeoutError:
                break
            if key.search(message.content):
                k += 1
            x += max(0.0, min(10.0, float(match.group(1))))
            self.pool.task_done()

        if k < kmin or n < nmin:
            return

        mean = x / n

        set_max = mean > self.max
        set_min = mean < self.min
        if set_max:
            self.max = mean
        if set_min:
            self.min = mean

        payload = Payload(mean, n, max=set_max, min=set_min)

        self.create_task(self.post(channel, payload))

    async def post(self, channel: Channel, payload: Payload) -> None:
        """Notify `channel` of a successful aggregation result"""
        nickname = self.CHANNEL_NICKNAME

        count = payload.count
        mean  = payload.mean

        best = payload.max and not payload.min
        if best:
            splash = f"best one today, {nickname}!"
        elif mean <= 2.5:
            splash = f"awful one, {nickname}"
        elif mean <= 5.0:
            splash = f"good attempt, {nickname}"
        elif mean <= 7.5:
            splash = f"nice one, {nickname}!"
        else:
            splash = f"incredible, {nickname}!"

        negative_emotes = self.NEGATIVE_EMOTES
        positive_emotes = self.POSITIVE_EMOTES

        emote = random.choice(positive_emotes if best or mean > 5.0 else negative_emotes)

        self.create_task(channel.send(f"DANKIES 🔔 {count:d} chatters rated this ad segue an average of {mean:.2f}/10 - {splash} {emote}"))

    @Cog.event()
    async def event_message(self, message: Message) -> None:
        """Add a message to the aggregation pool if applicable"""
        name = self.CHANNEL_NAME
        if message.echo or message.channel.name != name:
            return

        val = self.VAL
        if (match := val.search(message.content)):
            self.pool.put_nowait((message, match))

            func = self.aggregate
            if func.__name__ not in self.tasks:
                self.create_task(
                    func(message.channel), name=func.__name__,
                )
