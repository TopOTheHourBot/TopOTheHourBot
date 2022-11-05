import asyncio
import random
import re

from twitchio import Message
from twitchio.ext.commands import Bot, Context, command

from .utilities import TimeoutQueue, aenumerate


class TopOTheHourBot(Bot):

    KEY_PATTERN = re.compile(r"DANKIES|PogO|TomatoTime")
    VAL_PATTERN = re.compile(r"(-?\d+(?:\.\d*)?)\s?/\s?10")

    __slots__ = (
        "moderators",
        "timeout",
        "count",
        "negative_emotes",
        "positive_emotes",
        "mean_queue",
        "mean_max",
        "mean_task",
    )

    def __init__(
        self,
        token: str,
        *,
        client_secret: str,
        moderators: set[str],
        channel: str = "hasanabi",
        timeout: float = 9.5,
        count: int = 20,
        negative_emotes: tuple[str, ...] = ( "Sadge",  "FeelsBadMan",   "widepeepoSad", "unPOGGERS", "PogO", "😔"),
        positive_emotes: tuple[str, ...] = ("Gladge", "FeelsOkayMan", "widepeepoHappy",   "POGGERS", "PogU", "😳"),
    ) -> None:
        super().__init__(token, client_secret=client_secret, prefix="$", initial_channels=(channel,))

        self.moderators = moderators
        self.timeout = timeout
        self.count = count
        self.negative_emotes = negative_emotes
        self.positive_emotes = positive_emotes

        self.mean_queue = TimeoutQueue()
        self.mean_max   = 0.0
        self.mean_task  = None

    @command()
    async def ping(self, ctx: Context) -> None:
        await ctx.send(f"@{ctx.author.name} pong")

    @command()
    async def echo(self, ctx: Context) -> None:
        match ctx.message.content.split():
            case [_, *words]:
                await ctx.send(f"@{ctx.author.name} (echo): {' '.join(words)}")
            case _:
                raise RuntimeError("bad invoke")

    @command()
    async def code(self, ctx: Context) -> None:
        match ctx.message.content.split():
            case [_, *names]:
                names = map(lambda name: name if name.startswith('@') else f"@{name}", names)
                await ctx.send(f"{' '.join(names)} the bot's source code can be found on its Twitch profile Okayge")
            case _:
                raise RuntimeError("bad invoke")

    # XXX: Debating on whether to keep this enabled or not

    # async def event_ready(self):
    #     for channel in self.connected_channels:
    #         await channel.send(
    #             "Bot online - use DANKIES , PogO , or TomatoTime with a score out of 10 to rate an ad segue! "
    #             "(further conditions apply, read more on my profile)"
    #         )

    async def event_message(self, message: Message) -> None:
        if message.echo:
            return

        name    = message.author.name
        channel = message.channel
        content = message.content

        pending = not (self.mean_task is None or self.mean_task.done())

        if (match := self.VAL_PATTERN.search(content)) and (pending or self.KEY_PATTERN.search(content)):
            score = max(0.0, min(10.0, float(match.group(1))))

            self.mean_queue.put_nowait(score)

            if not pending:

                async def mean():
                    sum = 0.0
                    async for n, score in aenumerate(
                        self.mean_queue.consume(timeout=self.timeout),
                        start=1,
                    ):
                        sum += score
                    if n < self.count: return

                    mean = round(sum / n, ndigits=2)
                    mean_max = self.mean_max

                    if mean > mean_max:
                        self.mean_max = mean
                        splash = "best one today, hassy!"
                        emotes = self.positive_emotes
                    elif mean <= 2.5:
                        splash = "awful one, hassy"
                        emotes = self.negative_emotes
                    elif mean <= 5.0:
                        splash = "good attempt, hassy"
                        emotes = self.negative_emotes
                    elif mean <= 7.5:
                        splash = "nice one, hassy!"
                        emotes = self.positive_emotes
                    else:
                        splash = "incredible, hassy!"
                        emotes = self.positive_emotes

                    emote = random.choice(emotes)

                    await channel.send(f"DANKIES 🔔 {n} chatters rated this ad segue an average of {mean}/10 - {splash} {emote}")

                self.mean_task = asyncio.create_task(mean())

        if name in self.moderators:
            await self.handle_commands(message)

    async def event_command_error(self, ctx: Context, error: Exception) -> None:
        await ctx.send(f"@{ctx.author.name} {error}")
