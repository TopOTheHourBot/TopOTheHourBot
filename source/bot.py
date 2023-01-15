import random
import time
from typing import Optional

from twitchio import Message
from twitchio.ext.commands import Bot, Context, command

from .splits.batch_averager import BatchAverager, BatchAveragerResult

__all__ = ["TopOTheHourBot"]


class TopOTheHourBot(Bot):

    MODERATORS: set[str] = {"braedye", "bytesized_", "emjaye"}

    __slots__ = ()

    def __init__(
        self,
        token: str,
        *,
        prefix: str = "$",
        client_secret: Optional[str] = None,
        initial_channels: Optional[tuple[str, ...]] = None,
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
        self.add_cog(BatchAverager(self, channel="hasanabi", callbacks=(send_chat,)))

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


async def send_chat(result: BatchAveragerResult) -> None:
    emotes = (
        (
            "Sadge",
            "widepeepoSad",
            "unPOGGERS",
            "😔",
            "Awkward",
            "peepoPogO",
            "hasCringe",
            "🫵 LULW",
            "smHead",
        ),
        (
            "Gladge",
            "widepeepoHappy",
            "POGGERS",
            "😳",
            "pugPls",
            "peepoPog",
            "DRUMMING",
            "pepeWoah",
            "HYPERPOGGER",
        ),
    )

    averager = result.averager
    partial  = result.partial

    score = partial.complete()
    count = partial.count

    emote = random.choice(emotes[score > 5.0])

    if score <= 2.5:
        splash = "awful one, hassy"
    elif score <= 5.0:
        splash = "good attempt, hassy"
    elif score <= 7.5:
        splash = "nice one, hassy!"
    else:
        splash = "incredible, hassy!"

    content = f"DANKIES 🔔 {count} chatters rated this ad segue an average of {score:.2f}/10 - {splash} {emote}"

    await averager.channel.send(content)


async def send_post(result: BatchAveragerResult) -> None:  # TODO: hasanhub integration / callback
    ...
