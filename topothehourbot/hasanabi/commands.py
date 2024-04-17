from __future__ import annotations

__all__ = ["on_client_message"]

from typing import cast

from ircv3.twitch import ServerMessage

from ..api import checks
from ..api.client import Client
from ..api.commands import Match, ParameterError
from .common import commands, room


@checks.walled()
@checks.roomed(room)
async def on_client_message(client: Client, message: ServerMessage) -> None:
    match commands.match(message):

        case Match(name="ping"):
            await client.message(message, f"{client.latency:.0f}ms")

        case Match(name="copy", parameters={"words": words}):
            words = " ".join(cast(list[str], words))
            await client.message(message, words)

        case Match(name="code", parameters={"handles": handles}):
            handles = " ".join(cast(list[str], handles))
            await client.message(
                message,
                f"{handles} Okayge You can find the bot's source code on GitHub: https://github.com/TopOTheHourBot/",
            )

        case ParameterError() as error:
            await client.message(message, error)

        case _:
            return
