import asyncio
import logging
import random
import re
import uuid
from asyncio import Queue, TimeoutError
from collections.abc import Hashable

from twitchio import Channel, Message
from twitchio.ext.commands import Bot, Context, command
from twitchio.ext.routines import routine

logging.basicConfig(level=logging.INFO)

class CommandError(RuntimeError):
    pass


def clamp(x: float, lo: float = 0.0, hi: float = 10.0) -> float:
    return max(lo, min(hi, x))


class TopOTheHourBot(Bot):

    KEY = re.compile(r"DANKIES|PeepoWeen|PogO|TomatoTime")
    VAL = re.compile(r"(?P<value>-?\d{1,16}(?:\.\d*)?)\s?/\s?10")

    def __init__(
        self,
        token: str,
        *,
        client_secret: str,
        moderators: set[str],
        channel: str = "hasanabi",
        decay: float = 10.0,
        count: int = 15,
        negative_emotes: tuple[str, ...] = ( "Sadge",  "FeelsBadMan",   "widepeepoSad", "unPOGGERS", "PogO", "😔"),
        positive_emotes: tuple[str, ...] = ("Gladge", "FeelsOkayMan", "widepeepoHappy",   "POGGERS", "PogU", "😳"),
    ) -> None:
        super().__init__(token, client_secret=client_secret, prefix="$", initial_channels=(channel,))
        self.moderators: set[str] = moderators
        self.decay: float = decay
        self.count: int   = count
        self.negative_emotes: tuple[str, ...] = negative_emotes
        self.positive_emotes: tuple[str, ...] = positive_emotes

        self.active: bool = False
        self.mean_buffer: Queue[tuple[Hashable, float]] = Queue()
        self.mean_max: float = 0.0

    @routine(iterations=1)
    async def mean(self, channel: Channel) -> None:
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
        self.active = True

    @mean.after_routine
    async def mean_after(self) -> None:
        self.active = False

    @command()
    async def proxy(self, ctx: Context) -> None:
        content = ctx.message.content
        match content.split():
            case [_, token, *_]:
                if (match := self.VAL.match(token)):
                    name  = uuid.uuid4()
                    score = clamp(float(match.group("value")))
                    self.mean_buffer.put_nowait((name, score))
                    return
        raise CommandError(f"Usage: {ctx.prefix}proxy (type:float/10)")

    @command()
    async def ping(self, ctx: Context) -> None:
        name = ctx.author.name
        await ctx.send(f"@{name} pong")

    @command()
    async def echo(self, ctx: Context) -> None:
        name    = ctx.author.name
        content = ctx.message.content
        match content.split():
            case [_, *words]:
                await ctx.send(f"@{name} (echo): {' '.join(words)}")

    @command()
    async def shadow(self, ctx: Context) -> None:
        content = ctx.message.content
        match content.split():
            case [_, *words]:
                await ctx.send(' '.join(words))

    @command()
    async def set(self, ctx: Context) -> None:
        name    = ctx.author.name
        content = ctx.message.content
        match content.split():
            case [_, "decay", token, *_]:
                try:
                    decay = float(token)
                except ValueError:
                    pass
                else:
                    self.decay = decay
                    await ctx.send(f"@{name} Decay time set to {decay} seconds")
                    return
            case [_, "count", token, *_]:
                try:
                    count = int(token)
                except ValueError:
                    pass
                else:
                    self.count = count
                    await ctx.send(f"@{name} Minimum chatter count set to {count}")
                    return
        raise CommandError(f"Usage: {ctx.prefix}set (decay|count) (type:float|type:int)")

    async def event_command_error(self, ctx: Context, error: Exception) -> None:
        name = ctx.author.name
        await ctx.send(f"@{name} {error}")

    async def event_message(self, message: Message) -> None:
        if message.echo:
            return

        name    = message.author.name
        content = message.content

        active = self.active

        if (match := self.VAL.search(content)) and (active or self.KEY.search(content)):
            score = clamp(float(match.group("value")))
            self.mean_buffer.put_nowait((name, score))
            if not active:
                self.mean.start(message.channel)

        if name in self.moderators:
            await self.handle_commands(message)


if __name__ == "__main__":
    token = ...
    client_secret = ...

    bot = TopOTheHourBot(
        token,
        client_secret=client_secret,
        moderators={"braedye", "bytesized_", "emjaye"},
    )
    bot.run()
