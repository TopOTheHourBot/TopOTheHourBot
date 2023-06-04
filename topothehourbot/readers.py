from __future__ import annotations

import random
import re
from abc import abstractmethod
from collections.abc import Sequence
from re import Pattern
from typing import Any, Final, Protocol

from .client import Reader, TaskManager
from .client.ircv3 import IRCv3Package
from .client.streams import IStreamBase, OStreamBase, UnboundedIOStream


class Channel(Reader[IRCv3Package, str]):

    # Commands whose first argument is a channel name
    # See: https://dev.twitch.tv/docs/irc/commands/
    FILTERED_COMMANDS: Final[frozenset[str]] = {
        "PRIVMSG",
        "CLEARCHAT",
        "CLEARMSG",
        "HOSTTARGET",
        "NOTICE",
        "ROOMSTATE",
        "USERNOTICE",
        "USERSTATE",
    }

    __slots__ = ("name", "readers", "prefix")

    name: str
    readers: Sequence[ChannelReader]
    prefix: str

    def __init__(self, name: str, readers: Sequence[ChannelReader], prefix: str = "!") -> None:
        self.name = name if name.startswith("#") else f"#{name}"
        self.readers = readers
        self.prefix = prefix

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r}, readers={self.readers!r}, prefix={self.prefix!r})"

    def __str__(self) -> str:
        return self.name

    async def __call__(self, packages: IStreamBase[IRCv3Package], messages: OStreamBase[str]) -> Any:
        tasks = TaskManager()
        reader_streams = [
            UnboundedIOStream[IRCv3Package]()
            for _ in range(len(self.readers))
        ]
        for reader, reader_stream in zip(self.readers, reader_streams):
            tasks.create_task(reader(self, reader_stream, messages))
        async for package in packages.get_each():
            if package.command not in self.FILTERED_COMMANDS:
                continue
            if package[0] != self.name:
                continue
            for reader_stream in reader_streams:
                reader_stream.put(package)


class ChannelReader(Protocol):

    @abstractmethod
    async def __call__(self, channel: Channel, packages: IStreamBase[IRCv3Package], messages: OStreamBase[str], /) -> Any:
        raise NotImplementedError


class SegueRatingAggregator(ChannelReader):

    RATING_PATTERN: Final[Pattern[str]] = re.compile(
        r"""
        (?:^|\s)              # should proceed the beginning or whitespace
        (?P<value>
            (?:\d|10\.?)      # any integer within range 0 to 10
            |                 # or
            (?:\d?\.\d+)      # any decimal within range 0 to 9
        )
        \s?/\s?10             # denominator of 10
        (?:$|[\s,.!?])        # should precede the end, whitespace, or some punctuation
        """,
        re.VERBOSE | re.ASCII,
    )

    __slots__ = ("max_delay", "min_count")

    max_delay: float
    min_count: int

    def __init__(self, *, max_delay: float = 8.0, min_count: int = 50) -> None:
        self.max_delay = max_delay
        self.min_count = min_count

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(max_delay={self.max_delay!r}, min_count={self.min_count!r})"

    async def __call__(self, channel: Channel, packages: IStreamBase[IRCv3Package], messages: OStreamBase[str]) -> Any:
        while True:
            count, value = await (
                packages
                    .get_each()
                    .filter(lambda package: package.command == "PRIVMSG")
                    .map(lambda package: package[1])
                    .map(lambda body: self.RATING_PATTERN.search(body))
                    .not_none()
                    .timeout(self.max_delay)
                    .map(lambda match: match.group("value"))
                    .map(float)
                    .reduce((0, 0.0), lambda result, value: (result[0] + 1, result[1] + value))
            )
            if count >= self.min_count:
                message = "PRIVMSG {channel} :{body}".format(
                    channel=channel,
                    body=self.create_message_body(rating=value / count, count=count),
                ),
                messages.put(message)

    def create_message_body(self, rating: float, count: int) -> str:
        if rating <= 5.0:
            emote = random.choice(
                (
                    "unPOGGERS",
                    "Awkward BobaTime",
                    "hasCringe",
                    "PoroSad",
                    "Concerned Clap",
                    "Weirdge TeaTime",
                    "WTFF",
                    "👉 PainsChamp 👈",
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
                    "Okayge",
                    "peepoPog Clap",
                    "daphCheer",
                    "peepoCheer",
                    "peepoLegs peepoBlush",
                    "pokiBop",
                    "LFGO",
                ),
            )
            if rating <= 7.5:
                splash = "not bad, hassy!"
            else:
                splash = "incredible, hassy!"
        return (
            f"DANKIES 🔔 {count} chatters rated this ad segue an average "
            f"of {rating:.2f}/10 - {splash} {emote}"
        )


class PeepoClapCounter(ChannelReader):

    __slots__ = ("max_delay", "min_count")

    max_delay: float
    min_count: int

    def __init__(self, *, max_delay: float = 8.0, min_count: int = 25) -> None:
        self.max_delay = max_delay
        self.min_count = min_count

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(max_delay={self.max_delay!r}, min_count={self.min_count!r})"

    async def __call__(self, channel: Channel, packages: IStreamBase[IRCv3Package], messages: OStreamBase[str]) -> Any:
        while True:
            count = await (
                packages
                    .get_each()
                    .filter(lambda package: package.command == "PRIVMSG")
                    .map(lambda package: package[1])
                    .filter(lambda body: "peepoClap" in body)
                    .timeout(self.max_delay)
                    .count()
            )
            if count >= self.min_count:
                message = "PRIVMSG {channel} :{body}".format(
                    channel=channel,
                    body=self.create_message_body(count=count),
                ),
                messages.put(message)

    def create_message_body(self, count: int) -> str:
        return f"peepoClap 🔔 hasan has fathered {count} chatters"
