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
                            Role, VariadicParamSpec, handle_factory)

name: Final[str] = "hasanabi"
room: Final[str] = "#" + name

commands = (
    CommandGroup(prefix="$")
        .add_spec(
            name="ping",
            spec=CommandSpec(role=Role.VIP),
        )
        .add_spec(
            name="copy",
            spec=CommandSpec(role=Role.VIP)
                .add_spec(
                    name="words",
                    spec=VariadicParamSpec(),
                )
        )
        .add_spec(
            name="code",
            spec=CommandSpec(role=Role.VIP)
                .add_spec(
                    name="handles",
                    spec=VariadicParamSpec(factory=handle_factory)
                )
        )
        .add_spec(
            name="report",
            spec=CommandSpec(role=Role.VIP)
                .add_spec(
                    name="words",
                    spec=VariadicParamSpec(),
                )
        )
)

async def on_client_welcome(client: Client, command: Welcome) -> None:
    await client.join(room)

@checks.walled()
@checks.roomed(room)
async def on_client_message(client: Client, command: ServerMessage) -> None:
    match commands.match(command):
        case Match(command="ping"):
            await client.message(command, f"{client.latency:.0f}ms")
        case Match(command="copy", parameters={"words": words}):
            comment = " ".join(cast(list[str], words))
            await client.message(command, comment)
        case Match(command="code", parameters={"handles": handles}):
            handles = cast(list[str], handles)
            if handles:
                comment_header = " ".join(handles) + " "
            else:
                comment_header = ""
            await client.message(
                command,
                comment_header
                + "Okayge You can find the bot's source code on GitHub: "
                  "https://github.com/TopOTheHourBot/",
            )
        case Match(command="report", parameters={"words": words}):
            comment = " ".join(cast(list[str], words))
            await client.message(
                "#lyystra",
                f"{command.sender.handle} (sent from {command.room}): {comment}",
            )
        case ParameterError() as error:
            await client.message(command, error)
        case _:
            return
