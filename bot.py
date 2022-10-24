import asyncio
import logging
import random
import re
import uuid
from asyncio import Queue, TimeoutError
from collections.abc import Hashable
from typing import SupportsFloat, SupportsIndex

from twitchio import Channel, Message
from twitchio.ext.commands import Bot, Context, command
from twitchio.ext.routines import routine

logging.basicConfig(level=logging.INFO)

class CommandError(RuntimeError):
    """Raised on invalid command syntax"""
    pass


def clamp(x: SupportsIndex | SupportsFloat | str, lo: float = 0.0, hi: float = 10.0) -> float:
    """Return `x` clamped between `lo` and `hi`, inclusively"""
    return max(lo, min(hi, float(x)))


class TopOTheHourBot(Bot):
    """A simple Twitch bot that averages scores submitted to a user's channel

    "Scores" are defined as being a fraction whose denominator is 10, written
    (vaguely) like "X/10". The term, X, can be any number - including values
    below 0 or above 10.

    For the bot to begin averaging, a user must submit a message containing a
    score and "key". This key is defined as being one of the following emotes:
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
        count: int = 15,
        negative_emotes: tuple[str, ...] = ( "Sadge",  "FeelsBadMan",   "widepeepoSad", "unPOGGERS", "PogO", "😔"),
        positive_emotes: tuple[str, ...] = ("Gladge", "FeelsOkayMan", "widepeepoHappy",   "POGGERS", "PogU", "😳"),
    ) -> None:
        super().__init__(token, client_secret=client_secret, prefix="$", initial_channels=(channel,))
        self.moderators: set[str] = moderators
        self.decay: float = decay
        self.count: int = count
        self.negative_emotes: tuple[str, ...] = negative_emotes
        self.positive_emotes: tuple[str, ...] = positive_emotes

        self.mean_buffer: Queue[tuple[Hashable, float]] = Queue()
        self.mean_max: float = 0.0
        self.active: bool = False

    @routine(iterations=1)
    async def mean(self, channel: Channel) -> None:
        """Wait for, and average the scores put into `mean_buffer`, sending a
        message to `channel`

        The execution of this method signifies that a tallying phase has begun.
        Items must be placed into the `mean_buffer` within intervals of `decay`
        seconds.

        The message will only be sent if `count` or more unique scores were
        tallied (uniqueness being determined by the hashable object that should
        be the first item of each tuple within the mean buffer).
        """
        seen = set()
        m = n = 0

        while True:
            try:
                id, score = await asyncio.wait_for(self.mean_buffer.get(), timeout=self.decay)
            except TimeoutError:
                break
            else:
                if id not in seen:
                    m += score
                    n += 1
                    seen.add(id)
                self.mean_buffer.task_done()

        if n >= self.count:
            mean = round(m / n, ndigits=2)
            mean_max = self.mean_max

            if mean > mean_max:
                self.mean_max = mean
                splash = "best one today, hassy!"
                emotes = self.positive_emotes
            elif mean <= 2.0:
                splash = "awful one, hassy"
                emotes = self.negative_emotes
            elif mean <= 5.0:
                splash = "good attempt, hassy"
                emotes = self.negative_emotes
            elif mean <= 8.0:
                splash = "nice one, hassy!"
                emotes = self.positive_emotes
            else:
                splash = "incredible, hassy!"
                emotes = self.positive_emotes
            emote = random.choice(emotes)

            await channel.send(f"PeepoWeen 🔔 {n} chatters rated this ad segue an average of {mean}/10 - {splash} {emote}")

    @mean.before_routine
    async def mean_before(self) -> None:
        """Sets the `active` state to true"""
        self.active = True

    @mean.after_routine
    async def mean_after(self) -> None:
        """Sets the `active` state to false"""
        self.active = False

    @command()
    async def proxy(self, ctx: Context) -> None:
        """Submit a score to `mean_buffer` using a proxy identifier"""
        content = ctx.message.content
        match content.split():
            case [_, token, *_]:
                match = self.VAL.match(token)
                if match:
                    self.mean_buffer.put_nowait((
                        uuid.uuid4(),
                        clamp(match.group("value")),
                    ))
                    return
        raise CommandError("Bad invoke")

    # This exists mainly as a way to check the bot's live status. Note that the
    # TwitchIO client will automatically defer messages if certain rate limits
    # are reached. Thus, an absent reply may not always mean that the bot is in
    # an unresponsive state.

    @command()
    async def ping(self, ctx: Context) -> None:
        """Respond with pong"""
        name = ctx.author.name
        await ctx.send(f"@{name} pong")

    @command()
    async def echo(self, ctx: Context) -> None:
        """Write a message as the bot, signifying that the message came from
        the command's user
        """
        name    = ctx.author.name
        content = ctx.message.content
        match content.split():
            case [_, *words]:
                await ctx.send(f"@{name} (echo): {' '.join(words)}")

    @command()
    async def shadow(self, ctx: Context) -> None:
        """Write a message as the bot"""
        content = ctx.message.content
        match content.split():
            case [_, *words]:
                await ctx.send(' '.join(words))

    @command()
    async def set(self, ctx: Context) -> None:
        """Set the `decay`, `count`, or `mean_max` attributes"""
        name    = ctx.author.name
        content = ctx.message.content
        match content.split():
            case [_, "decay", token, *_]:
                self.decay = float(token)
                await ctx.send(f"@{name} Decay time set to {self.decay} seconds")
                return
            case [_, "count", token, *_]:
                self.count = int(token)
                await ctx.send(f"@{name} Minimum chatter count set to {self.count}")
                return
            case [_, "max", token, *_]:
                self.mean_max = float(token)
                await ctx.send(f"@{name} Maximum score set to {self.mean_max}")
                return
        raise CommandError("Bad invoke")

    async def event_command_error(self, ctx: Context, error: Exception) -> None:
        """Send the error message raised by a command failure to the command's
        user
        """
        name = ctx.author.name
        await ctx.send(f"@{name} {error}")

    async def event_message(self, message: Message) -> None:
        """Search for, and manage scores submitted to the connected channel"""
        if message.echo:
            return

        name    = message.author.name
        content = message.content

        active = self.active

        if (match := self.VAL.search(content)) and (active or self.KEY.search(content)):
            score = clamp(match.group("value"))

            self.mean_buffer.put_nowait((name, score))
            if not active:
                self.mean.start(message.channel)

        if name in self.moderators:
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
