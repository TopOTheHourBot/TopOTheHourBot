from __future__ import annotations

__all__ = ["channel"]

import random
from decimal import Decimal
from typing import cast

from ircv3.twitch import ServerMessage

from .api import commands
from .api.client import Channel, ChannelWriter
from .api.commands import (CommandGroup, CommandSpec, Match, ParameterError,
                           Role, VariadicParamSpec)
from .api.utilities import Buffer
from .utilities import Rating

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
)

@channel.message_signal.callback
async def on_channel_message_command(writer: ChannelWriter, message: ServerMessage) -> None:
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

@channel.message_signal.callback
async def on_channel_message_rating(writer: ChannelWriter, command: ServerMessage) -> None:
    if (
        writer.client.name == command.sender.name
        or (rating := Rating.from_message(command)) is None
    ):
        return

    with (
        writer
            .channel
            .message_signal
            .remove_callback(on_channel_message_rating, temporary=True)
    ):
        ratings = Buffer[Rating]()
        ratings.send(rating)

        async def send_rating_to_buffer(writer: ChannelWriter, command: ServerMessage) -> None:
            if (
                writer.client.name != command.sender.name
                and (rating := Rating.from_message(command)) is not None
            ):
                ratings.send(rating)

        with (
            writer
                .channel
                .message_signal
                .add_callback(send_rating_to_buffer, temporary=True)
        ):
            count, sum = await (
                aiter(ratings)
                    .finite_timeout(8.5)
                    .global_unique(lambda rating: rating.id)
                    .map(lambda rating: rating.value)
                    .reduce((0, Decimal()), lambda x, y: (x[0] + 1, x[1] + y))
            )

    if count < 40:
        return

    mean = sum / count

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
