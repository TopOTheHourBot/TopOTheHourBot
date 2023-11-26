from __future__ import annotations

__all__ = ["TopOTheHourBot"]

import random
import re
from collections.abc import Coroutine, Iterator
from dataclasses import dataclass
from decimal import Decimal
from re import Pattern
from typing import Any, Final, Literal, Optional, final, overload, override

from ircv3 import IRCv3ServerCommandProtocol
from ircv3.dialects import twitch
from ircv3.dialects.twitch import (LocalServerCommand, ServerPrivateMessage,
                                   SupportsClientProperties)

from .system import Client, SubClient, Summarizer


@final
class TopOTheHourBot(Client):

    __slots__ = ()
    name: Final[Literal["topothehourbot"]] = "topothehourbot"

    @override
    def paraludes(self) -> Iterator[Coroutine[Any, Any, None]]:
        yield HasanAbiRoomer(self).run()


@final
class HasanAbiRoomer(
    SubClient[TopOTheHourBot, LocalServerCommand],  # type: ignore
    SupportsClientProperties,
):

    __slots__ = ()
    name: Final[Literal["hasanabi"]] = "hasanabi"

    @override
    def mapper(self, command: IRCv3ServerCommandProtocol) -> Optional[LocalServerCommand]:
        if (
            twitch.is_local_server_command(command)
            and (self.room == command.room)
        ):
            return command

    @override
    def prelude(self) -> Coroutine[Any, Any, None]:
        return self.source_client.join(self.room)

    @override
    def paraludes(self) -> Iterator[Coroutine[Any, Any, None]]:
        yield RatingAverager(self).run()

    @override
    def postlude(self) -> Coroutine[Any, Any, None]:
        return self.source_client.part(self.room)

    @overload
    async def message(self, message: ServerPrivateMessage, comment: str, /, *, important: bool = False) -> None: ...
    @overload
    async def message(self, comment: str, /, *, important: bool = False) -> None: ...

    async def message(self, *args: ServerPrivateMessage | str, important: bool = False) -> None:
        n = len(args)
        if n == 2:
            message, comment = args
            assert isinstance(message, ServerPrivateMessage)
            assert isinstance(comment, str)
            return await self.source_client.message(
                message,
                comment,
                important=important,
            )
        if n == 1:
            comment, = args
            assert isinstance(comment, str)
            return await self.source_client.message(
                self.room,
                comment,
                important=important,
            )
        raise TypeError(f"expected 1 or 2 positional arguments, got {n}")


@final
@dataclass(init=False, slots=True)
class PartialAverage:

    value: Decimal
    count: int

    def __init__(self, value: Decimal | str | float | int, count: int = 1) -> None:
        self.value = Decimal(value)
        self.count = count

    def __add__(self, other: PartialAverage) -> PartialAverage:
        return PartialAverage(
            value=self.value + other.value,
            count=self.count + other.count,
        )

    def evaluate(self) -> Decimal:
        return self.value / self.count


class RatingAverager(Summarizer[HasanAbiRoomer, PartialAverage, PartialAverage]):

    __slots__ = ()
    initial: Final[PartialAverage] = PartialAverage(0, 0)
    timeout: Final[float] = 8.5
    rating_pattern: Final[Pattern[str]] = re.compile(
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
        flags=re.ASCII | re.VERBOSE,
    )

    @property
    def client(self) -> TopOTheHourBot:
        """Same as ``self.source_client.source_client``"""
        return self.source_client.source_client

    @property
    def roomer(self) -> HasanAbiRoomer:
        """Same as ``self.source_client``"""
        return self.source_client

    @override
    def mapper(self, command: LocalServerCommand) -> Optional[PartialAverage]:
        if (
            twitch.is_server_private_message(command)
            and (self.client.name != command.sender.name)  # Echo
            and (match := self.rating_pattern.search(command.comment))
        ):
            return PartialAverage(match.group(1))

    @override
    def reducer(self, summation: PartialAverage, summand: PartialAverage) -> PartialAverage:
        return summation + summand

    @override
    def predicator(self, summation: PartialAverage) -> bool:
        return summation.count >= 40

    @override
    async def finalizer(self, summation: PartialAverage) -> None:
        average = summation.evaluate()

        if average <= 5:
            emote = random.choice(
                (
                    "unPOGGERS",
                    "Awkward BobaTime",
                    "hasCringe",
                    "PoroSad",
                    "Concerned Clap",
                    "Dead",
                    "HuhChamp TeaTime",
                    "HUHH",
                ),
            )
            if average <= 2.5:
                splash = "awful one, hassy"
            else:
                splash = "uhm.. good attempt, hassy"
        else:
            emote = random.choice(
                (
                    "Gladge PETTHEHASAN",
                    "peepoHappy",
                    "peepoPog Clap",
                    "chatPls",
                    "peepoCheer",
                    "peepoBlush",
                    "Jigglin",
                    "veryCat",
                ),
            )
            if average <= 7.5:
                splash = "not bad, hassy"
            else:
                splash = "incredible, hassy!"

        await self.roomer.message(
            f"DANKIES 🔔 {summation.count} chatters rated this ad segue an "
            f"average of {average:.2f}/10 - {splash} {emote}",
            important=True,
        )
