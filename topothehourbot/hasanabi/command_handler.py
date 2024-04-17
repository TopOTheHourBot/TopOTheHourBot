from __future__ import annotations

__all__ = ["on_channel_message"]

from typing import cast

from ircv3.twitch import ServerMessage

from ..api import checks, commands
from ..api.client import ClientWriter
from ..api.commands import (CommandGroup, CommandSpec, Match, ParameterError,
                            Role, VariadicParamSpec)
from .globals import room

command_group = (
    CommandGroup(prefix="$")
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

@checks.walled()
@checks.roomed(room)
async def on_channel_message(writer: ClientWriter, message: ServerMessage) -> None:
    match command_group.match(message):

        case Match(name="ping"):
            await writer.message(message, f"{writer.latency:.0f}ms")

        case Match(name="copy", parameters={"words": words}):
            words = " ".join(cast(list[str], words))
            await writer.message(message, words)

        case Match(name="code", parameters={"handles": handles}):
            handles = " ".join(cast(list[str], handles))
            await writer.message(
                message,
                f"{handles} Okayge You can find the bot's source code on GitHub: https://github.com/TopOTheHourBot/",
            )

        case ParameterError() as error:
            await writer.message(message, error)

        case _:
            return
