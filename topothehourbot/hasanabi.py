from __future__ import annotations

__all__ = ["app"]

import random

from ircv3.dialects.twitch import ServerMessage

from .api.app import ChannelApp
from .api.client import Channel
from .api.commands import CommandGroup, Success
from .rating_finder import RatingBatch, RatingFinder

rating_finder = RatingFinder()

@rating_finder.success_signal.callback
async def on_rating_finder_success(channel: Channel, ratings: RatingBatch) -> None:
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

    await channel.message(
        f"DANKIES 🔔 {count:,d} chatters rated this ad segue an average"
        f" of {mean:.2f}/10 - {reaction}",
    )

app = (
    ChannelApp("hasanabi")
        .load(rating_finder)
)

@app.message_signal.callback
async def on_channel_message(
    channel: Channel,
    message: ServerMessage,
    *,
    commands: CommandGroup = CommandGroup(prefix="$").add_command(name="ping"),
) -> None:
    if channel.client.name == message.sender.name:
        return
    match commands.parse(message.comment):
        case Success(name="ping"):
            await channel.message(
                "pong",
                target=message,
            )
        case _:
            return
