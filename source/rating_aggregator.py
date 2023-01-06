import asyncio
import itertools
import random
import re
from asyncio import Queue, Task, TimeoutError
from collections.abc import Coroutine
from re import Match, Pattern
from typing import Optional

from twitchio import Channel, Message
from twitchio.ext.commands import Bot, Cog

__all__ = ["RatingAggregator"]


class RatingAggregator(Cog):

    CHANNEL_NAME: str = "hasanabi"
    CHANNEL_NICKNAME: str = "hassy"

    PATTERN: Pattern[str] = re.compile(r"(-?\d+(?:\.\d*)?)\s?/\s?10")
    TIMEOUT: float = 9
    DENSITY: int = 50

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
        "🫵 LULW",
        "smHead",
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
        "DRUMMING",
        "pepeWoah",
        "HYPERPOGGER",
    )

    __slots__ = ("bot", "tasks", "matches")

    def __init__(self, bot: Bot) -> None:
        self.bot = bot
        self.tasks: dict[str, Task] = {}

        self.matches: Queue[Match[str]] = Queue()

    def create_task(self, coro: Coroutine, *, name: Optional[str] = None) -> None:
        task = asyncio.create_task(coro, name=name)

        name = task.get_name()  # Get the task's name in case we weren't provided one
        self.tasks[name] = task

        task.add_done_callback(lambda task: self.tasks.pop(task.get_name()))

    async def aggregate(self, channel: Channel) -> None:
        sum = 0.0
        for count in itertools.count():
            try:
                match = await asyncio.wait_for(self.matches.get(), timeout=self.TIMEOUT)
            except TimeoutError:
                break
            sum += clamp(float(match.group(1)), lower=0.0, upper=10.0)
            self.matches.task_done()
        if count < self.DENSITY: return

        mean = sum / count

        nickname = self.CHANNEL_NICKNAME
        if mean <= 2.5:
            splash = f"awful one, {nickname}"
        elif mean <= 5.0:
            splash = f"good attempt, {nickname}"
        elif mean <= 7.5:
            splash = f"nice one, {nickname}!"
        else:
            splash = f"incredible, {nickname}!"

        emote = random.choice(self.POSITIVE_EMOTES if mean > 5.0 else self.NEGATIVE_EMOTES)

        await channel.send(f"DANKIES 🔔 {count:d} chatters rated this ad segue an average of {mean:.2f}/10 - {splash} {emote}")

    @Cog.event()
    async def event_message(self, message: Message) -> None:
        if message.echo:
            return
        if message.channel.name != self.CHANNEL_NAME:
            return
        if (match := self.PATTERN.search(message.content)):
            self.matches.put_nowait(match)
            if (name := (func := self.aggregate).__name__) not in self.tasks:
                self.create_task(func(message.channel), name=name)


def clamp(x: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, x))
