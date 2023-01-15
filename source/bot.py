import random
import re
import time
import uuid
from typing import Optional
from uuid import UUID

from aiohttp import ClientSession
from twitchio import Message
from twitchio.ext.commands import Bot, Context, command

from .keys import (HASANHUB_CLIENT_SECRET, TWITCH_ACCESS_TOKEN,
                   TWITCH_CLIENT_SECRET)
from .splits.batch_averager import BatchAverager, BatchAveragerResult

__all__ = ["TopOTheHourBot"]

STREAM_UUID: UUID = uuid.uuid4()


class TopOTheHourBot(Bot):

    MODERATORS: set[str] = {"braedye", "bytesized_", "emjaye"}

    __slots__ = ()

    def __init__(
        self,
        token: str = TWITCH_ACCESS_TOKEN,
        *,
        prefix: str = "$",
        client_secret: Optional[str] = TWITCH_CLIENT_SECRET,
        initial_channels: Optional[tuple[str, ...]] = ("hasanabi",),
        heartbeat: Optional[float] = 30,
        retain_cache: Optional[bool] = True,
        **kwargs,
    ) -> None:
        super().__init__(
            token,
            prefix=prefix,
            client_secret=client_secret,
            initial_channels=initial_channels,
            heartbeat=heartbeat,
            retain_cache=retain_cache,
            **kwargs,
        )

        async def chat(result: BatchAveragerResult) -> None:
            score = result.partial.complete()
            count = result.partial.count

            if score <= 2.5:
                splash = "awful one, hassy"
            elif score <= 5.0:
                splash = "good attempt, hassy"
            elif score <= 7.5:
                splash = "nice one, hassy!"
            else:
                splash = "incredible, hassy!"

            if score <= 5.0:
                emote = random.choice((
                    "Sadge", "widepeepoSad", "unPOGGERS", "😔", "Awkward",
                    "peepoPogO", "hasCringe", "🫵 LULW", "smHead",
                ))
            else:
                emote = random.choice((
                    "Gladge", "widepeepoHappy", "POGGERS", "😳", "pugPls",
                    "peepoPog", "DRUMMING", "pepeWoah", "HYPERPOGGER",
                ))

            await result.averager.channel.send(
                f"DANKIES 🔔 {count} chatters rated this ad segue an average "
                f"of {score:.2f}/10 - {splash} {emote}",
            )

        async def post(result: BatchAveragerResult) -> None:
            score = result.partial.complete()
            epoch = time.time()

            async with ClientSession() as session:
                async with session.post(
                    "https://hasanhub.com/api/add-top-of-the-hour-rating",
                    json={
                        "rating": round(score, ndigits=2),
                        "timestamp": round(epoch, ndigits=None),
                        "streamUuid": str(STREAM_UUID),
                        "secret": str(HASANHUB_CLIENT_SECRET),
                    },
                ) as response:
                    response.raise_for_status()

        self.add_cog(BatchAverager(
            self,
            channel="hasanabi",
            pattern=re.compile(
                r"((?<!\d|-)(?:\d?\.\d+|\d|10))\s?/\s?10",
                flags=re.ASCII,
            ),
            callbacks=(chat, post),
        ))

    @command(aliases=["p"])
    async def ping(self, ctx: Context) -> None:
        await ctx.send(f"{ctx.author.mention} pong")

    @command(aliases=["c", "echo"])
    async def copy(self, ctx: Context, *words: str) -> None:
        await ctx.send(f"{ctx.author.mention} (copy): {' '.join(words)}")

    @command()
    async def code(self, ctx: Context, *names: str) -> None:
        names = map(lambda name: name if name.startswith("@") else f"@{name}", names)
        await ctx.send(f"{' '.join(names)} the bot's source code can be found on its Twitch profile Okayge")

    async def event_command_error(self, ctx: Context, error: Exception) -> None:
        await ctx.send(f"{ctx.author.mention} {error}")

    async def event_message(self, message: Message) -> None:
        if message.echo:
            return
        if message.author.name in self.MODERATORS:
            await self.handle_commands(message)
