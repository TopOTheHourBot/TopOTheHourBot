from __future__ import annotations

__all__ = [
    "DEFAULT_PICKLE_DIRECTORY",
    "main",
]

import pickle
from asyncio import TaskGroup
from pathlib import Path
from typing import Final

import websockets

from .core import TopOTheHourBot, TopOTheHourBotConfiguration
from .extensions import HasanAbiExtension, HasanAbiExtensionConfiguration

URI: Final[str] = "ws://irc-ws.chat.twitch.tv:80"

DEFAULT_PICKLE_DIRECTORY: Final[Path] = Path(__file__).parent / "pickles"

TOPOTHEHOURBOT_CONFIGURATION_PICKLE_FILE: Final[str] = "TopOTheHourBotConfiguration.pickle"
HASANABI_EXTENSION_CONFIGURATION_PICKLE_FILE: Final[str] = "HasanAbiExtensionConfiguration.pickle"


async def main(
    oauth_token: str,
    *,
    pickle_directory: Path = DEFAULT_PICKLE_DIRECTORY,
) -> None:
    """Run TopOTheHourBot forever

    Requires a Twitch OAuth token. See the Twitch Developers documentation for
    details on generating one: https://dev.twitch.tv/docs/irc/authenticate-bot/

    Some client extensions make use of pickling to save and restore instance
    data between sessions of execution. By default, pickles are stored in a
    "pickles" folder located in this file's parent directory. This location may
    be changed via ``pickle_directory``. The directory is always created if it
    does not already exist.
    """
    pickle_directory = pickle_directory.resolve()
    pickle_directory.mkdir(exist_ok=True)
    async for connection in websockets.connect(URI):
        client = TopOTheHourBot(
            connection=connection,
            config=TopOTheHourBotConfiguration.from_pickle(
                path=pickle_directory / TOPOTHEHOURBOT_CONFIGURATION_PICKLE_FILE,
                raise_not_found=False,
            ),
        )
        hasanabi_extension = HasanAbiExtension(
            client=client,
            config=HasanAbiExtensionConfiguration.from_pickle(
                path=pickle_directory / HASANABI_EXTENSION_CONFIGURATION_PICKLE_FILE,
                raise_not_found=False,
            ),
        )
        await client.send("CAP REQ :twitch.tv/commands twitch.tv/membership twitch.tv/tags")
        await client.send(f"PASS oauth:{oauth_token}")
        await client.send(f"NICK {client.name}")
        try:
            async with TaskGroup() as tasks:
                tasks.create_task(hasanabi_extension.distribute())
                await client.distribute()
        finally:
            hasanabi_extension.config.into_pickle(
                path=pickle_directory / HASANABI_EXTENSION_CONFIGURATION_PICKLE_FILE,
                protocol=pickle.HIGHEST_PROTOCOL,
            )
            client.config.into_pickle(
                path=pickle_directory / TOPOTHEHOURBOT_CONFIGURATION_PICKLE_FILE,
                protocol=pickle.HIGHEST_PROTOCOL,
            )
