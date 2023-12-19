from __future__ import annotations

__all__ = [
    "DEFAULT_PICKLE_DIRECTORY",
    "main",
]

from asyncio import TaskGroup
from contextlib import ExitStack
from pathlib import Path
from typing import Final

from . import system
from .core import HasanAbiExtension, TopOTheHourBot

DEFAULT_PICKLE_DIRECTORY: Final[Path] = Path(__file__).parent / "pickles"


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
    assert pickle_directory.is_dir()
    pickle_directory.mkdir(exist_ok=True)
    async for client in system.connect(TopOTheHourBot, oauth_token=oauth_token):
        with ExitStack() as stack:
            extension_contexts = [
                HasanAbiExtension.from_pickle(
                    client=client,
                    path=pickle_directory / "HasanAbi.pickle",
                ),
            ]
            async with TaskGroup() as tasks:
                for extension in map(stack.enter_context, extension_contexts):
                    tasks.create_task(extension.distribute())
                await client.distribute()
