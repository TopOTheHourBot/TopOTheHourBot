from __future__ import annotations

__all__ = ["TopOTheHourBot"]

import os
import random
import re
from collections.abc import Coroutine, Iterator
from dataclasses import dataclass
from decimal import Decimal
from re import Pattern
from typing import Any, Final, Literal, Optional, final, override

from ircv3 import IRCv3ServerCommandProtocol
from ircv3.dialects import twitch
from ircv3.dialects.twitch import ClientPrivateMessage

from .system import Client, Localizer, Summarizer


@final
class TopOTheHourBot(Client):

    __slots__ = ()
    source_name: Final[Literal["topothehourbot"]] = "topothehourbot"

    @property
    @override
    def oauth_token(self) -> str:
        oauth_token = os.getenv("TWITCH_OAUTH_TOKEN")
        assert oauth_token is not None
        return oauth_token

    @override
    def interludes(self) -> Iterator[Coroutine[Any, Any, None]]:
        yield HasanAbiLocalizer(self).run()


@final
class HasanAbiLocalizer(Localizer):

    __slots__ = ()
    room: Final[Literal["#hasanabi"]] = "#hasanabi"

    @override
    def interludes(self) -> Iterator[Coroutine[Any, Any, None]]:
        yield RatingAverager(self).run()


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


class RatingAverager(Summarizer[HasanAbiLocalizer, PartialAverage, PartialAverage]):

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

    @override
    def mapper(self, command: IRCv3ServerCommandProtocol) -> Optional[PartialAverage]:
        if (
            not twitch.is_server_private_message(command)
            or self.client.source_name == command.sender.source_name
        ):
            return
        if (match := self.rating_pattern.search(command.comment)):
            return PartialAverage(match.group(1))

    @override
    def reducer(self, summation: PartialAverage, summand: PartialAverage) -> PartialAverage:
        return summation + summand

    @override
    async def finalizer(self, summation: PartialAverage) -> None:
        if summation.count < 40:
            return

        rating = summation.evaluate()

        if rating <= 5:
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
            if rating <= 2.5:
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
            if rating <= 7.5:
                splash = "not bad, hassy"
            else:
                splash = "incredible, hassy!"

        command = ClientPrivateMessage(
            self.client.room,
            f"DANKIES 🔔 {summation.count} chatters rated this ad segue an "
            f"average of {rating:.2f}/10 - {splash} {emote}",
        )

        await self.client.send(command)
