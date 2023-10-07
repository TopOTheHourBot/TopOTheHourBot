from __future__ import annotations

import random
import re
from asyncio import TaskGroup
from dataclasses import dataclass
from re import Pattern
from typing import Final, Literal

from channels import SupportsRecv, SupportsSend
from ircv3 import IRCv3CommandProtocol
from ircv3.dialects.twitch import Join, Privmsg

from ..pipe import Pipe

RATING_PATTERN: Final[Pattern[str]] = re.compile(
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


@dataclass(frozen=True, slots=True)
class PartialAverage:

    sum: float
    count: int = 1

    def __bool__(self) -> bool:
        return self.count != 0

    def compound(self, other: PartialAverage, /) -> PartialAverage:
        return PartialAverage(self.sum + other.sum, self.count + other.count)

    def complete(self) -> float:
        return self.sum / self.count


class HasanAbiPipe(Pipe):

    ROOM: Final[Literal["#hasanabi"]] = "#hasanabi"

    __slots__ = ()

    async def __call__(
        self,
        istream: SupportsRecv[IRCv3CommandProtocol],
        ostream: SupportsSend[IRCv3CommandProtocol | str],
    ) -> None:
        await ostream.send(Join(self.ROOM))
        async with TaskGroup() as tasks:
            async for command in (
                istream
                    .recv_each()
                    .filter(lambda command: command.name == "PRIVMSG")
                    .filter(lambda command: command.room == self.ROOM)  # type: ignore
            ):
                assert isinstance(command, Privmsg)

    async def rating_average(
        self,
        istream: SupportsRecv[IRCv3CommandProtocol],
        ostream: SupportsSend[IRCv3CommandProtocol | str],
    ) -> None:
        async with TaskGroup() as tasks:
            while (
                partial_average := await istream
                    .recv_each()
                    .map(lambda command: command.arguments[1])
                    .map(RATING_PATTERN.search)
                    .not_none()
                    .timeout(8.5)
                    .map(lambda match: match.group(1))
                    .map(float)
                    .map(PartialAverage)
                    .reduce(PartialAverage(0, 0), PartialAverage.compound)
            ):
                if partial_average.count < 50:
                    continue

                average = partial_average.complete()

                if average <= 5.0:
                    emote = random.choice(
                        (
                            "unPOGGERS",
                            "Awkward BobaTime",
                            "hasCringe",
                            "PoroSad",
                            "Concerned Clap",
                            "Dead",
                            "HuhChamp",
                            "Jupijejnt",
                            "MikePensive",
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
                            "Jupijej",
                            "veryCat",
                        ),
                    )
                    if average <= 7.5:
                        splash = "not bad, hassy"
                    else:
                        splash = "incredible, hassy!"

                command = Privmsg(
                    self.ROOM,
                    f"DANKIES 🔔 {partial_average.count} chatters rated this ad"
                    f" segue an average of {average:.2f}/10 - {splash} {emote}",
                )

                tasks.create_task(ostream.send(command))
