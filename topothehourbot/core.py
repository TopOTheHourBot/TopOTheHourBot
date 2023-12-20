from __future__ import annotations

__all__ = [
    "TopOTheHourBot",
    "HasanAbiExtension",
]

import asyncio
import operator
import pickle
import random
import re
from asyncio import TaskGroup
from collections.abc import AsyncIterator, Coroutine, Iterator
from contextlib import contextmanager
from pathlib import Path
from re import Pattern
from typing import Any, Final, Literal, Optional, Self, override

from ircv3.dialects import twitch
from ircv3.dialects.twitch import LocalServerCommand

from .system import IRCv3Client, IRCv3ClientExtension
from .system.pipes import Series
from .utilities import DecimalCounter, IntegerCounter


class TopOTheHourBot(IRCv3Client):
    """The TopOTheHourBot client"""

    __slots__ = ()
    name: Final[Literal["topothehourbot"]] = "topothehourbot"


class HasanAbiExtension(IRCv3ClientExtension[LocalServerCommand]):
    """TopOTheHourBot's Hasan-specific operations

    Does a few different things:
    - Defines a small set of mod-only commands
    - Averages batch ratings given by chat when Hasan performs an ad segue
    - Sums batch +1 and -1 scores given by chat when Hasan distinctively stays
      in and out of character during roleplay sessions

    Contains only one instance variable, ``roleplay_rating_total``, that is the
    summation of all roleplay scores across time. All other attributes are
    statically-defined at the class level.
    """

    __slots__ = ("roleplay_rating_total")
    target: Final[Literal["#hasanabi"]] = "#hasanabi"

    def __init__(
        self,
        client: IRCv3Client | IRCv3ClientExtension[Any],
        *,
        roleplay_rating_total: int = 0,
    ) -> None:
        """Construct an extension instance"""
        super().__init__(client)
        self.roleplay_rating_total = roleplay_rating_total

    @classmethod
    @contextmanager
    def from_pickle(
        cls,
        client: IRCv3Client | IRCv3ClientExtension[Any],
        *,
        path: Path,
        protocol: Optional[int] = pickle.HIGHEST_PROTOCOL,
    ) -> Iterator[Self]:
        """Return a context manager that safely loads and dumps the extension's
        instance data as a pickle file, yielding the extension instance

        Uses the defaults defined by ``__init__()`` if the file pointed to by
        ``path`` is not found.
        """
        try:
            with open(path, mode="rb") as file:
                state = pickle.load(file)
        except FileNotFoundError:
            state = {}
        assert isinstance(state, dict)
        self = cls(client, **state)
        try:
            yield self
        finally:
            state = {"roleplay_rating_total": self.roleplay_rating_total}
            with open(path, mode="wb") as file:
                pickle.dump(state, file, protocol)

    @Series.compose
    async def handle_commands(self) -> AsyncIterator[Coroutine]:
        """Handle traditional call-and-respond commands

        Commands are set to only be usable by me (Lyystra/Astryyl), some
        friends, and the mod team. This might be subject to change.
        """
        with self.attachment() as pipe:
            async for message in (
                aiter(pipe)
                    .filter(twitch.is_server_private_message)
                    .filter(lambda message: (
                        message.sender.name in {
                            "lyystra",
                            "astryyl",
                            "emjaye",
                            "bytesized_",
                        }
                        or message.sender.is_moderator
                        or message.sender.is_owner
                    ))
            ):
                match message.comment.split():
                    case ["$ping", *_]:
                        yield self.message(
                            f"{self.latency:.0f}ms",
                            target=message,
                            important=True,
                        )
                    case ["$copy" | "$shadow", *words]:
                        yield self.message(
                            " ".join(words),
                            target=message,
                            important=True,
                        )
                    case ["$roleplay_rating_total", *handles]:
                        yield self.message(
                            f"{" ".join(map(lambda handle: "@" + handle.lstrip("@"), handles))}"
                            f" hassy has accrued {self.roleplay_rating_total:,d} roleplay points"
                            f" since December 17, 2023",
                            target=message,
                            important=True,
                        )

    segue_rating_initial: Final[DecimalCounter] = DecimalCounter(0, 0)
    segue_rating_pattern: Final[Pattern[str]] = re.compile(
        r"""
        (?:^|\s)              # should proceed the beginning or whitespace
        (
            (?:(?:\d|10)\.?)  # any integer within range 0 to 10
            |
            (?:\d?\.\d+)      # any decimal within range 0 to 9
        )
        \s?/\s?10             # denominator of 10
        (?:$|[\s,.!?])        # should precede the end, whitespace, or some punctuation
        """,
        flags=re.VERBOSE,
    )

    @Series.compose
    async def handle_segue_ratings(self) -> AsyncIterator[Coroutine]:
        """Handle ad segue ratings

        Averages the numerator of values in the form "X/10", where "X" is a
        number between 0 and 10 (inclusive), typically given by chat when Hasan
        segues into running an advertisement on the broadcast.
        """
        with self.attachment() as pipe:
            async for segue_rating, segue_rating_count in (
                Series.repeat_while(
                    lambda: (
                        aiter(pipe)
                            .filter(twitch.is_server_private_message)
                            .filter(lambda message: (
                                message.sender.name != self.name
                            ))
                            .map(lambda message: (
                                self.segue_rating_pattern.search(message.comment)
                            ))
                            .not_none()
                            .map(lambda match: (
                                DecimalCounter(match.group(1))
                            ))
                            .finite_timeout(8.5)
                            .reduce(self.segue_rating_initial, operator.add)
                    ),
                    lambda counter: counter.count,
                )
                .filter(lambda counter: counter.count >= 40)
                .map(lambda counter: (
                    counter.value / counter.count,
                    counter.count,
                ))
            ):
                if segue_rating <= 5:
                    if segue_rating <= 2.5:
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
                    if segue_rating <= 7.5:
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
                yield self.message(
                    f"DANKIES 🔔 {segue_rating_count:d} chatters rated this ad segue an average of"
                    f" {segue_rating:.2f}/10 - {random.choice(reactions)}",
                    target=self.target,
                    important=True,
                )

    roleplay_rating_total: int
    roleplay_rating_initial: Final[IntegerCounter] = IntegerCounter(0, 0)
    roleplay_rating_pattern: Final[Pattern[str]] = re.compile(
        r"""
        (?:^|\s)        # should proceed the beginning or whitespace
        ([-+]1)         # -1 or +1
        (?:$|[\s,.!?])  # should precede the end, whitespace, or some punctuation
        """,
        flags=re.VERBOSE,
    )

    @Series.compose
    async def handle_roleplay_ratings(self) -> AsyncIterator[Coroutine]:
        """Handle roleplay ratings

        Sums values in the form "+1" or "-1", typically given by chat to award
        or penalise Hasan for staying in and out of character during roleplay
        sessions.
        """
        with self.attachment() as pipe:
            async for roleplay_rating_delta in (
                Series.repeat_while(
                    lambda: (
                        aiter(pipe)
                            .filter(twitch.is_server_private_message)
                            .filter(lambda message: (
                                message.sender.name != self.name
                            ))
                            .map(lambda message: (
                                self.roleplay_rating_pattern.search(message.comment)
                            ))
                            .not_none()
                            .map(lambda match: (
                                IntegerCounter(match.group(1))
                            ))
                            .finite_timeout(8)
                            .reduce(self.roleplay_rating_initial, operator.add)
                    ),
                    lambda counter: counter.count,
                )
                .filter(lambda counter: counter.count >= 20)
                .map(lambda counter: counter.value)
            ):
                roleplay_rating_total = self.roleplay_rating_total + roleplay_rating_delta
                self.roleplay_rating_total = roleplay_rating_total
                if roleplay_rating_total > 0:
                    reactions = (
                        "FeelsSnowyMan",
                        ":D",
                        "Gladge",
                        "veryCat",
                    )
                else:
                    reactions = (
                        "FeelsSnowMan",
                        ":(",
                        "Sadge",
                        "Awkward",
                    )
                yield self.message(
                    f"donScoot 🔔 hassy {"gained" if roleplay_rating_delta >= 0 else "lost"}"
                    f" {roleplay_rating_delta:+,d} points for this roleplay moment - hassy has"
                    f" {roleplay_rating_total:,d} points in total {random.choice(reactions)}",
                    target=self.target,
                    important=True,
                )

    async def accumulate(self) -> None:
        """Execute all message handlers asynchronously, dispatching coroutines
        as they are yielded
        """
        async with TaskGroup() as tasks:
            async for coro in (
                self.handle_commands()
                    .merge(
                        self.handle_segue_ratings(),
                        self.handle_roleplay_ratings(),
                    )
            ):
                tasks.create_task(coro)

    async def distribute(self) -> None:
        """Join the target room and eternally distribute its localised commands
        to attachments
        """
        await self.join(self.target)
        accumulator = asyncio.create_task(self.accumulate())
        with self._diverter.closure() as diverter:
            with self._client.attachment() as pipe:
                async for command in (
                    aiter(pipe)
                        .filter(twitch.is_local_server_command)
                        .filter(lambda command: command.room == self.target)
                ):
                    diverter.send(command)
        await accumulator
