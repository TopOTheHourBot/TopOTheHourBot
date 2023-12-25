from __future__ import annotations

__all__ = [
    "DEFAULT_PICKLE_DIRECTORY",
    "main",
]

import pickle
from asyncio import TaskGroup
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Optional

from . import system
from .core import HasanAbiExtension, TopOTheHourBot

DEFAULT_PICKLE_DIRECTORY: Final[Path] = Path(__file__).parent / "pickles"


@dataclass(slots=True)
class HasanAbiExtensionParameters:
    """Persistent objects to save and load for ``HasanAbiExtension``"""

    roleplay_rating_total: int = 0


def load_pickle[DefaultT](path: Path, *, default: DefaultT = None) -> Any | DefaultT:
    """Load a pickled object from ``path``

    Returns ``default`` if the file pointed to by ``path`` is not found.
    """
    try:
        with open(path, mode="rb") as file:
            return pickle.load(file)
    except FileNotFoundError:
        return default


def save_pickle(path: Path, object: Any, *, protocol: Optional[int] = pickle.HIGHEST_PROTOCOL) -> None:
    """Save a pickled object to ``path``

    ``protocol`` argument passed to ``pickle.dump()`` - see its docstring for
    more details.
    """
    with open(path, mode="wb") as file:
        pickle.dump(object, file, protocol)


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
        parameters: HasanAbiExtensionParameters = load_pickle(
            pickle_directory / "HasanAbi.pickle",
            default=HasanAbiExtensionParameters(),
        )
        extension = HasanAbiExtension(
            client=client,
            roleplay_rating_total=parameters.roleplay_rating_total,
        )
        try:
            async with TaskGroup() as tasks:
                tasks.create_task(extension.distribute())
                await client.distribute()
        finally:
            save_pickle(
                pickle_directory / "HasanAbi.pickle",
                HasanAbiExtensionParameters(extension.roleplay_rating_total),
            )
