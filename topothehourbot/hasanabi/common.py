from __future__ import annotations

__all__ = [
    "name",
    "room",
    "commands",
    "on_client_welcome",
    "on_client_message",
]

from typing import Final, cast

from ircv3.common import Welcome
from ircv3.twitch import ServerMessage

from ..api import checks
from ..api.client import Client
from ..api.commands import (CommandGroup, CommandSpec, Match, ParameterError,
                            Role, VariadicParamSpec, handle)

name: Final[str] = "hasanabi"
room: Final[str] = "#" + name

commands = (
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
                    spec=VariadicParamSpec(factory=handle)
                )
        )
)

async def on_client_welcome(client: Client, command: Welcome) -> None:
    await client.join(room)

@checks.walled()
@checks.roomed(room)
async def on_client_message(client: Client, command: ServerMessage) -> None:
    match commands.match(command):
        case Match(name="ping"):
            await client.message(command, f"{client.latency:.0f}ms")
        case Match(name="copy", parameters={"words": words}):
            words = " ".join(cast(list[str], words))
            await client.message(command, words)
        case Match(name="code", parameters={"handles": handles}):
            handles = " ".join(cast(list[str], handles))
            await client.message(
                command,
                f"{handles} Okayge You can find the bot's source code on GitHub: https://github.com/TopOTheHourBot/",
            )
        case ParameterError() as error:
            await client.message(command, error)
        case _:
            return
