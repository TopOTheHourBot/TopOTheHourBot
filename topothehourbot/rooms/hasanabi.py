from __future__ import annotations

import random
import re
from asyncio import TaskGroup
from dataclasses import dataclass
from re import Pattern
from typing import Final, Literal

from channels import Channel, SupportsRecv, SupportsSend
from ircv3 import IRCv3CommandProtocol
from ircv3.dialects import twitch
from ircv3.dialects.twitch import ClientJoin, ClientPrivmsg, ServerPrivmsg

from ..pipes import Pipe, Transport

ROOM: Final[Literal["#hasanabi"]] = "#hasanabi"

RATING_TIMEOUT: Final[float] = 8.5
RATING_DENSITY: Final[int] = 50
RATING_PATTERN: Final[Pattern[str]] = re.compile(
    r"""
    (?:^|\s)              # should proceed the beginning or whitespace
    (
        (?:(?:\d|10)\.?)  # any integer within range 0 to 10
        |
        (?:\d?\.\d+)      # any decimal within range 0 to 9
    )
    \s?/\s?10             # denominator of 10
    (?:$|[\s,.!?])        # should precede the end, whitespace, or punctuation
    """,
    flags=re.ASCII | re.VERBOSE,
)


@dataclass(slots=True)
class PartialAverage:

    sum: float
    count: int = 1

    def __bool__(self) -> bool:
        return self.count != 0

    def compound(self, other: PartialAverage, /) -> PartialAverage:
        return PartialAverage(self.sum + other.sum, self.count + other.count)

    def complete(self) -> float:
        return self.sum / self.count


class HasanAbi(Pipe):

    __slots__ = ()

    async def __call__(
        self,
        isstream: SupportsRecv[IRCv3CommandProtocol],
        omstream: SupportsSend[IRCv3CommandProtocol | str],
        osstream: SupportsSend[IRCv3CommandProtocol | str],
    ) -> None:
        await osstream.send(ClientJoin(ROOM))
        transports = [
            Transport(
                self.rating_average,
                Channel[ServerPrivmsg](),
                omstream=omstream,
                osstream=osstream,
            ),
        ]
        async with TaskGroup() as tasks:
            for transport in transports:
                tasks.create_task(transport.open())
            async for command in (
                isstream
                    .recv_each()
                    .filter(twitch.is_privmsg)
                    .filter(lambda command: command.room == ROOM)
            ):
                for transport in transports:
                    tasks.create_task(transport.send(command))

    async def rating_average(
        self,
        isstream: SupportsRecv[ServerPrivmsg],
        omstream: SupportsSend[IRCv3CommandProtocol | str],
        osstream: SupportsSend[IRCv3CommandProtocol | str],
    ) -> None:
        while (
            partial_average := await isstream
                .recv_each()
                .map(lambda command: command.comment)
                .map(RATING_PATTERN.search)
                .not_none()
                .timeout(RATING_TIMEOUT)
                .map(lambda match: match.group(1))
                .map(float)
                .map(PartialAverage)
                .reduce(PartialAverage(0, 0), PartialAverage.compound)
        ):
            if partial_average.count < RATING_DENSITY:
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

            command = ClientPrivmsg(
                ROOM,
                f"DANKIES 🔔 {partial_average.count} chatters rated this ad"
                f" segue an average of {average:.2f}/10 - {splash} {emote}",
            )

            async with TaskGroup() as tasks:
                tasks.create_task(omstream.send(command))
