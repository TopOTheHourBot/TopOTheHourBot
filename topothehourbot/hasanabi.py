from __future__ import annotations

__all__ = ["channel"]

import random
from typing import cast

from ircv3.dialects.twitch import ServerMessage

from .api.client import Channel, ChannelWriter
from .api.commands import CommandGroup, CommandSpec, HandleParamSpec, Success
from .rating_finder import Rating, RatingBatch, RatingFinder

rating_finder = RatingFinder()

@rating_finder.success_signal.callback
async def on_rating_finder_success(ratings: RatingBatch, /, writer: ChannelWriter, initial_rating: Rating) -> None:
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
    Channel(name="hasanabi")
        .add_callbacks(rating_finder)
)

commands = (
    CommandGroup(prefix="$")
        .add_command(name="ping")
        .add_command(
            name="code",
            spec=CommandSpec()
                .add_param(name="handle0", spec=HandleParamSpec())
                .add_param(name="handle1", spec=HandleParamSpec())
                .add_param(name="handle2", spec=HandleParamSpec())
        )
)

@channel.message_signal.callback
async def on_channel_message(writer: ChannelWriter, message: ServerMessage) -> None:
    if writer.client.name == message.sender.name:
        return
    match commands.parse(message.comment):
        case Success(name="ping"):
            await writer.message(
                f"{writer.latency:.0f}ms",
                target=message,
            )
        case Success(name="code", parameters=parameters):
            handles = " ".join(cast(dict[str, str], parameters).values())
            await writer.message(
                f"{handles} Okayge You can find the bot's source code on GitHub: https://github.com/TopOTheHourBot/",
                target=message,
            )
        case _:
            return
