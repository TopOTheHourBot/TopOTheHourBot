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
from ..api.commands import (CommandError, CommandGroup, CommandSpec, Match,
                            RequiredParamSpec, Role, room_factory)

name: Final[str] = "lyystra"
room: Final[str] = "#" + name

commands = (
    CommandGroup()
        .add_spec(
            name="ping",
            spec=CommandSpec(role=Role.NONE)
        )
        .add_spec(name="kill")
        .add_spec(
            name="join",
            spec=CommandSpec()
                .add_spec(
                    name="room",
                    spec=RequiredParamSpec(factory=room_factory),
                )
        )
        .add_spec(
            name="part",
            spec=CommandSpec()
                .add_spec(
                    name="room",
                    spec=RequiredParamSpec(factory=room_factory),
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
        case Match(name="kill"):
            await client.message(command, "Closing client process...")
            await client.close()
        case Match(name="join", parameters={"room": room}):
            await client.message(command, f"Joining {room}...")
            await client.join(cast(str, room))
        case Match(name="part", parameters={"room": room}):
            await client.message(command, f"Parting {room}...")
            await client.part(cast(str, room))
        case CommandError() as error:
            await client.message(command, error)
        case _:
            return
