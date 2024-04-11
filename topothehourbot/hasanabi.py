from __future__ import annotations

__all__ = ["channel"]

import random
from typing import cast

from ircv3.dialects.twitch import ServerMessage

from .api import commands
from .api.client import Channel, ChannelWriter
from .api.commands import (CommandGroup, CommandSpec, Match, ParameterError,
                           Role, VariadicParamSpec)
from .rating_finder import RatingBatch, RatingFinder

rating_finder = RatingFinder()

@rating_finder.batch_signal.callback
async def on_rating_finder_batch(writer: ChannelWriter, ratings: RatingBatch) -> None:
    count = ratings.count
    mean = ratings.mean

    assert count > 0
    assert mean is not None

    if mean <= 5:
        if mean <= 2.5:
            reactions = (
                "yikes, hassy .. unPOGGERS",
                "awful one, hassy :(",
                "that wasn't very, uhm .. good, hassy Concerned",
            )
        else:
            reactions = (
                "sorry, hassy .. :/",
                "uhm .. good try, hassy PoroSad",
                "not .. great, hassy .. Okayyy Clap",
            )
    else:
        if mean <= 7.5:
            reactions = (
                "not bad, hassy ! :D",
                "nice, hassy ! peepoPog Clap",
                "good one, hassy ! hasScoot",
            )
        else:
            reactions = (
                "incredible, hassy !! pepoDance",
                "holy smokes, hassy !! :O",
                "wowieee, hassy !! peepoExcite",
            )

    reaction = random.choice(reactions)

    await writer.message(
        f"DANKIES 🔔 {count:,d} chatters rated this ad segue an average of"
        f" {mean:.2f}/10 - {reaction}",
    )

channel = (
    Channel(
        name="hasanabi",
        commands=CommandGroup(prefix="$")
            .add_spec(
                name="ping",
                spec=CommandSpec(role=Role.MODERATOR),
            )
            .add_spec(
                name="copy",
                spec=CommandSpec(role=Role.MODERATOR)
                    .add_spec(
                        name="words",
                        spec=VariadicParamSpec(),
                    )
            )
            .add_spec(
                name="code",
                spec=CommandSpec(role=Role.MODERATOR)
                    .add_spec(
                        name="handles",
                        spec=VariadicParamSpec(factory=commands.handle)
                    )
            )
    )
    .add_callbacks(rating_finder)
)

@channel.message_signal.callback
async def on_channel_message(writer: ChannelWriter, message: ServerMessage) -> None:
    if writer.client.name == message.sender.name:
        return
    match writer.channel.commands.match(message):
        case Match(name="ping"):
            await writer.message(
                f"{writer.latency:.0f}ms",
                target=message,
            )
        case Match(name="copy", parameters={"words": words}):
            words = " ".join(cast(list[str], words))
            await writer.message(
                words,
                target=message,
            )
        case Match(name="code", parameters={"handles": handles}):
            handles = " ".join(cast(list[str], handles))
            await writer.message(
                f"{handles} Okayge You can find the bot's source code on GitHub: https://github.com/TopOTheHourBot/",
                target=message,
            )
        case ParameterError() as error:
            await writer.message(error, target=message)
        case _:
            return
