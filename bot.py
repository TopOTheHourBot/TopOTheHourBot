import asyncio
import logging
import random
import re
import uuid
from asyncio import Queue, TimeoutError
from collections.abc import Hashable
from typing import Any

from twitchio import Channel, Message
from twitchio.ext.commands import Bot, Context, command
from twitchio.ext.routines import routine

logging.basicConfig(
    format="[%(asctime)s] [%(name)s] %(message)s",
    level=logging.INFO,
)


class CommandError(RuntimeError):
    """Raised on bad command input"""
    pass


def clamp(x: Any, lo: float = 0.0, hi: float = 10.0) -> float:
    """Return `x` clamped between `lo` and `hi`, inclusively"""
    return max(lo, min(hi, float(x)))


class TopOTheHourBot(Bot):
    """A simple Twitch bot that averages scores submitted to a user's channel

    "Scores" are defined as being a fraction whose denominator is 10, written
    (vaguely) like "X/10". The term, X, can be any number - including values
    below 0 or above 10.

    For the bot to begin averaging, a user must submit a message containing a
    score and key. This "key" is defined as being one of the following emotes:
    - DANKIES (or some variation during holidays)
    - PogO
    - TomatoTime

    Scores that were sent prior to this initial message are not counted.

    This class knowingly breaks inheritance rules in order to keep its memory
    footprint low - it is designed to only operate under one channel.
    """

    KEY = re.compile(r"DANKIES|PeepoWeen|PogO|TomatoTime")
    VAL = re.compile(r"(?P<value>-?\d+(?:\.\d*)?)\s?/\s?10")

    def __init__(
        self,
        token: str,
        *,
        client_secret: str,
        moderators: set[str],
        channel: str = "hasanabi",
        decay: float = 9.0,
        count: int = 20,
        negative_emotes: tuple[str, ...] = ( "Sadge",  "FeelsBadMan",   "widepeepoSad", "unPOGGERS", "PogO", "😔"),
        positive_emotes: tuple[str, ...] = ("Gladge", "FeelsOkayMan", "widepeepoHappy",   "POGGERS", "PogU", "😳"),
    ) -> None:
        super().__init__(token, client_secret=client_secret, prefix="$", initial_channels=(channel,))
        self._moderators: set[str] = moderators
        self._decay: float = decay
        self._count: int = count
        self._negative_emotes: tuple[str, ...] = negative_emotes
        self._positive_emotes: tuple[str, ...] = positive_emotes

        self._mean_queue: Queue[tuple[Hashable, float]] = Queue()
        self._mean_max: float = 0.0
        self._pending: bool = False

    @property
    def decay(self) -> float:
        """The amount of time allowance between subsequent score discoveries,
        in seconds
        """
        return self._decay

    @decay.setter
    def decay(self, value: Any) -> None:
        value = float(value)
        if value <= 0:
            raise ValueError("decay time must be greater than 0 seconds")
        self._decay = value

    @property
    def count(self) -> int:
        """The minimum number of unique chatters needed for the average score
        to be sent to the connected channel
        """
        return self._count

    @count.setter
    def count(self, value: Any) -> None:
        value = int(value)
        if value <= 0:
            raise ValueError("minimum chatter count must be greater than 0")
        self._count = value

    @routine(iterations=1)
    async def mean(self, channel: Channel) -> None:
        """Wait for, and average the scores put into `_mean_queue`, sending the
        average to `channel`

        The execution of this method signifies that an averaging phase has
        begun. Items must be placed into `_mean_queue` within intervals of
        `_decay` seconds.

        The message will only be sent if `_count` or more unique scores were
        tallied (uniqueness being determined by the hashable object of each
        tuple).
        """
        seen = set()
        m = 0.0

        while True:
            try:
                hashable, score = await asyncio.wait_for(self._mean_queue.get(), timeout=self._decay)
            except TimeoutError:
                break
            else:
                if hashable not in seen:
                    m += score
                    seen.add(hashable)
                self._mean_queue.task_done()

        n = len(seen)

        logging.info(f"tallied {n} unique chatters")

        if n < self._count:
            return

        mean = round(m / n, ndigits=2)
        mean_max = self._mean_max

        if mean > mean_max:
            self._mean_max = mean
            splash = "best one today, hassy!"
            emotes = self._positive_emotes
        elif mean <= 2.0:
            splash = "awful one, hassy"
            emotes = self._negative_emotes
        elif mean <= 5.0:
            splash = "good attempt, hassy"
            emotes = self._negative_emotes
        elif mean <= 8.0:
            splash = "nice one, hassy!"
            emotes = self._positive_emotes
        else:
            splash = "incredible, hassy!"
            emotes = self._positive_emotes

        emote = random.choice(emotes)

        await channel.send(f"PeepoWeen 🔔 {n} chatters rated this ad segue an average of {mean}/10 - {splash} {emote}")

    @mean.before_routine
    async def mean_before(self) -> None:
        """Sets the `_pending` state to true"""
        self._pending = True
        logging.info("averaging phase started, result pending...")

    @mean.after_routine
    async def mean_after(self) -> None:
        """Sets the `_pending` state to false"""
        self._pending = False
        logging.info("...done")

    # This exists mainly as a way to check the bot's live status. Note that the
    # TwitchIO client will automatically defer messages if certain rate limits
    # are reached. Thus, an absent reply may not always mean that the bot is in
    # an unresponsive state.

    @command()
    async def ping(self, ctx: Context) -> None:
        """Respond with pong"""
        await ctx.send(f"@{ctx.author.name} pong")

    @command()
    async def proxy(self, ctx: Context) -> None:
        """Submit a score to `_mean_queue` using a proxy identifier"""
        match ctx.message.content.split():
            case [_, token, *_]:
                if (match := self.VAL.match(token)):
                    self._mean_queue.put_nowait((
                        uuid.uuid4(),
                        clamp(match.group("value")),
                    ))
            case _:
                raise CommandError("bad invoke")

    @command()
    async def echo(self, ctx: Context) -> None:
        """Write a message as the bot, signifying that the message came from
        the command's user
        """
        match ctx.message.content.split():
            case [_, *words]:
                await ctx.send(f"@{ctx.author.name} (echo): {' '.join(words)}")
            case _:
                raise CommandError("bad invoke")

    @command()
    async def shadow(self, ctx: Context) -> None:
        """Write a message as the bot"""
        match ctx.message.content.split():
            case [_, *words]:
                await ctx.send(' '.join(words))
            case _:
                raise CommandError("bad invoke")

    @command()
    async def set(self, ctx: Context) -> None:
        """Set a property's value"""
        match ctx.message.content.split():
            case [_, ("decay" | "count") as name, token, *_]:
                setattr(self, name, token)
                await ctx.send(f"@{ctx.author.name} attribute '{name}' set to {token}")
            case _:
                raise CommandError("bad invoke")

    async def event_command_error(self, ctx: Context, error: Exception) -> None:
        """Send the error message raised by a command to its user"""
        await ctx.send(f"@{ctx.author.name} {error}")

    async def event_message(self, message: Message) -> None:
        """Search for, and manage scores submitted to the connected channel"""
        if message.echo:
            return

        name    = message.author.name
        content = message.content
        channel = message.channel

        pending = self._pending

        if (match := self.VAL.search(content)) and (pending or self.KEY.search(content)):
            score = clamp(match.group("value"))

            self._mean_queue.put_nowait((name, score))
            if not pending:
                self.mean.start(channel, stop_on_error=False)  # Continue on error, otherwise mean_after() won't be called

        if name in self._moderators:
            await self.handle_commands(message)


if __name__ == "__main__":
    # Access and client secret tokens omitted for obvious reasons. See here for
    # more details: https://dev.twitch.tv/docs/irc
    token = ...
    client_secret = ...

    bot = TopOTheHourBot(
        token,
        client_secret=client_secret,
        moderators={"braedye", "bytesized_", "emjaye"},
    )
    bot.run()
