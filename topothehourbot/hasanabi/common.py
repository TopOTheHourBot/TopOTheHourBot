from __future__ import annotations

__all__ = [
    "name",
    "room",
    "commands",
    "on_client_welcome",
]

from typing import Final

from ircv3.common import Welcome

from ..api.client import Client
from ..api.commands import (CommandGroup, CommandSpec, Role, VariadicParamSpec,
                            handle)

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
