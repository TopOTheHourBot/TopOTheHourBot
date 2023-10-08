from __future__ import annotations

import random
import re
from asyncio import TaskGroup
from dataclasses import dataclass
from re import Pattern
from typing import Final

from channels import Channel, StopSend, SupportsRecv, SupportsSend
from ircv3 import IRCv3CommandProtocol
from ircv3.dialects import twitch
from ircv3.dialects.twitch import ClientJoin, ClientPrivmsg, ServerPrivmsg

from ..pipes import Pipe, Transport


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


class HasanAbi(Pipe[IRCv3CommandProtocol, IRCv3CommandProtocol | str, IRCv3CommandProtocol | str]):

    ROOM: Final[str] = "#hasanabi"
    DEBUG: Final[bool] = True

    async def __call__(
        self,
        isstream: SupportsRecv[IRCv3CommandProtocol],
        omstream: SupportsSend[IRCv3CommandProtocol | str],
        osstream: SupportsSend[IRCv3CommandProtocol | str],
    ) -> None:
        result = await osstream.try_send(ClientJoin(self.ROOM))
        if isinstance(result, StopSend):
            return
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
                    .filter(lambda command: command.room == self.ROOM)
            ):
                for transport in transports:
                    tasks.create_task(transport.send(command))

    RATING_KEY_EMOTE: Final[str] = "DANKIES"
    RATING_POSITIVE_EMOTES: Final[tuple[str, ...]] = (
        "Gladge PETTHEHASAN",
        "peepoHappy",
        "peepoPog Clap",
        "chatPls",
        "peepoCheer",
        "peepoBlush",
        "Jigglin",
        "Jupijej",
        "veryCat",
    )
    RATING_NEGATIVE_EMOTES: Final[tuple[str, ...]] = (
        "unPOGGERS",
        "Awkward BobaTime",
        "hasCringe",
        "PoroSad",
        "Concerned Clap",
        "Dead",
        "HuhChamp",
        "Jupijejnt",
        "MikePensive",
    )
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
                .map(self.RATING_PATTERN.search)
                .not_none()
                .timeout(self.RATING_TIMEOUT)
                .map(lambda match: match.group(1))
                .map(float)
                .map(PartialAverage)
                .reduce(PartialAverage(0, 0), PartialAverage.compound)
        ):
            if partial_average.count < self.RATING_DENSITY:
                continue

            average = partial_average.complete()

            if average <= 5.0:
                emote = random.choice(self.RATING_NEGATIVE_EMOTES)
                if average <= 2.5:
                    splash = "awful one, hassy"
                else:
                    splash = "uhm.. good attempt, hassy"
            else:
                emote = random.choice(self.RATING_POSITIVE_EMOTES)
                if average <= 7.5:
                    splash = "not bad, hassy"
                else:
                    splash = "incredible, hassy!"

            command = ClientPrivmsg(
                self.ROOM,
                f"{self.RATING_KEY_EMOTE} 🔔 {partial_average.count} chatters"
                f" rated this ad segue an average of {average:.2f}/10 -"
                f" {splash} {emote}",
            )

            await omstream.send(command)  # Might report to a DB in the future as well
