import logging
import random
import re
import uuid
from typing import Final, Optional
from uuid import UUID

from twitchio import Message
from twitchio.ext.commands import Bot, Context, command
from twitchio.ext.commands.errors import CommandNotFound

from .keys import TWITCH_ACCESS_TOKEN, TWITCH_CLIENT_SECRET
from .splits.batch_averager import BatchAverager, BatchAveragerResult

__all__ = ["TopOTheHourBot"]

SESSION_ID: Final[UUID] = uuid.uuid4()


class TopOTheHourBot(Bot):

    GLOBAL_MODERATORS: set[str] = {
        "lyystra",
        "astryyl",
        "bytesized_",
        "emjaye",
    }

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
                splash = "uhm.. good attempt, hassy"
            elif score <= 7.5:
                splash = "not bad, hassy"
            else:
                splash = "incredible, hassy!"

            if score <= 5.0:
                emote = random.choice(
                    (
                        "unPOGGERS",
                        "Awkward BobaTime",
                        "hasCringe",
                        "PoroSad",
                        "Concerned Clap",
                        "Dead",
                        "HuhChamp TeaTime",
                        "HUHH",
                    ),
                )
            else:
                emote = random.choice(
                    (
                        "Gladge PETTHEHASAN",
                        "peepoHappy",
                        "peepoPog Clap",
                        "chatPls",
                        "peepoCheer",
                        "peepoBlush",
                        "Jigglin",
                        "veryCat",
                    ),
               )

            await result.averager.channel.send(
                f"DANKIES 🔔 {count} chatters rated this ad segue an average "
                f"of {score:.2f}/10 - {splash} {emote}",
            )

        self.add_cog(BatchAverager(
            self,
            channel="hasanabi",
            density=40,
            pattern=re.compile(
                r"""
                (?:^|\s)            # should proceed the beginning or whitespace
                (
                  (?:(?:\d|10)\.?)  # any integer within range 0 to 10
                  |
                  (?:\d?\.\d+)      # any decimal within range 0 to 9
                )
                \s?/\s?10           # denominator of 10
                (?:$|[\s,.!?])      # should precede the end, whitespace, or some punctuation
                """,
                flags=re.ASCII | re.VERBOSE,
            ),
            callbacks=(chat,),
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
        if isinstance(error, CommandNotFound):
            return
        await ctx.send(f"{ctx.author.mention} {error}")

    async def event_ready(self) -> None:
        logging.info(f"Session ID is {SESSION_ID}")

    async def event_message(self, message: Message) -> None:
        if message.echo:
            return
        if message.author.name in self.GLOBAL_MODERATORS:
            await self.handle_commands(message)
