from __future__ import annotations

__all__ = ["main"]

import asyncio
import operator
import random
import re
from asyncio import TaskGroup
from collections.abc import AsyncIterator, Coroutine
from re import Pattern
from typing import Final, Literal, Optional, override

from ircv3.dialects import twitch
from ircv3.dialects.twitch import LocalServerCommand

from . import system
from .system import IRCv3Client, IRCv3ClientExtension
from .system.pipes import Series
from .utilities import DecimalCounter, IntegerCounter

# TODO: Update documentation


class TopOTheHourBot(IRCv3Client):

    name: Final[Literal["topothehourbot"]] = "topothehourbot"


class HasanAbiExtension(IRCv3ClientExtension[LocalServerCommand]):

    target: Final[Literal["#hasanabi"]] = "#hasanabi"

    @Series.compose
    async def handle_commands(self) -> AsyncIterator[Coroutine]:
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
                    case ["$copy" | "$shadow", *args]:
                        yield self.message(
                            " ".join(args),
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
        with self.attachment() as pipe:
            async for counter in (
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
            ):
                rating = counter.value / counter.count
                if rating <= 5:
                    if rating <= 2.5:
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
                    if rating <= 7.5:
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
                    f"DANKIES 🔔 {counter.count:d} chatters rated this ad segue an average"
                    f" of {rating:.2f}/10 - {random.choice(reactions)}",
                    target=self.target,
                    important=True,
                )

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
        with self.attachment() as pipe:
            async for counter in (
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
            ):
                rating = counter.value
                if rating:
                    if rating > 0:
                        reactions = (
                            "FeelsSnowyMan",
                            ":D",
                            "Gladge",
                        )
                    else:
                        reactions = (
                            "FeelsSnowMan",
                            ":(",
                            "Sadge",
                        )
                else:
                    reactions = ("Awkward ..",)
                yield self.message(
                    f"donScoot 🔔 hassy {"gained" if rating >= 0 else "lost"} {rating:+d}"
                    f" points for this roleplay moment {random.choice(reactions)}",
                    target=self.target,
                    important=True,
                )

    async def accumulate(self) -> None:
        async with TaskGroup() as tasks:
            async for coro in (
                self.handle_commands()
                    .merge(
                        self.handle_segue_ratings(),
                        self.handle_roleplay_ratings(),
                    )
            ):
                tasks.create_task(coro)

    @override
    async def distribute(self) -> None:
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


async def main(*, oauth_token: Optional[str] = None) -> None:
    async for client in system.connect(
        TopOTheHourBot,
        oauth_token=oauth_token,
    ):
        async with TaskGroup() as tasks:
            tasks.create_task(HasanAbiExtension(client).distribute())
            await client.distribute()
