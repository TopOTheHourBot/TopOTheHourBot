from __future__ import annotations

__all__ = ["on_client_message"]

import random
import re
from decimal import Decimal
from re import Pattern
from typing import ClassVar, Self

from ircv3.twitch import ServerMessage

from ..api import checks
from ..api.client import Client
from ..api.utilities import Buffer
from .common import room


class Rating:

    pattern: ClassVar[Pattern[str]] = re.compile(
        pattern=r"""
        (?:^|\s)                   # Should proceed the beginning or whitespace
        (
            [-+]?                  # Optional + or -
            (?:
                (?:\d+(?:\.\d*)?)  # Integer with optional decimal part
                |
                (?:\.\d+)          # Decimal part only
            )
        )
        \s?/\s?10                  # Denominator of 10
        (?:$|[\s,.!?])             # Should precede the end, whitespace, or some punctuation
        """,
        flags=re.VERBOSE,
    )
    value_max: ClassVar[Decimal] = Decimal("10")
    value_min: ClassVar[Decimal] = Decimal("0")

    __slots__ = ("_message", "_value", "_index_begin", "_index_end")
    _message: ServerMessage
    _value: Decimal
    _index_begin: int
    _index_end: int

    def __init__(
        self,
        message: ServerMessage,
        *,
        value: Decimal,
        index_begin: int,
        index_end: int,
    ) -> None:
        self._message = message
        self._value = value
        self._index_begin = index_begin
        self._index_end = index_end

    @classmethod
    def from_message(cls, message: ServerMessage) -> Self | None:
        match = cls.pattern.search(message.comment)
        if match is None:
            return
        value = max(min(Decimal(match.group(1)), cls.value_max), cls.value_min)
        index_begin, index_end = match.span(1)
        return cls(
            message,
            value=value,
            index_begin=index_begin,
            index_end=index_end,
        )

    @property
    def id(self) -> str:
        return self.message.sender.id

    @property
    def message(self) -> ServerMessage:
        return self._message

    @property
    def value(self) -> Decimal:
        return self._value

    @property
    def index_begin(self) -> int:
        return self._index_begin

    @property
    def index_end(self) -> int:
        return self._index_end


@checks.walled()
@checks.roomed(room)
async def on_client_message(client: Client, command: ServerMessage) -> None:
    rating = Rating.from_message(command)
    if rating is None:
        return

    with (
        client
            .app
            .message_signal
            .remove_callback(on_client_message, temporary=True)
    ) as message_signal:

        ratings = Buffer[Rating]()
        ratings.send(rating)

        @checks.walled()
        @checks.roomed(room)
        def send(client: Client, command: ServerMessage) -> None:
            rating = Rating.from_message(command)
            if rating is not None:
                ratings.send(rating)

        with message_signal.add_callback(send, temporary=True):
            count, sum = await (
                aiter(ratings)
                    .finite_timeout(8.5)
                    .global_unique(lambda rating: rating.id)
                    .map(lambda rating: rating.value)
                    .reduce(
                        (0, Decimal()),
                        lambda last, curr: (last[0] + 1, last[1] + curr),
                    )
            )

        if count < 40:
            return

        mean = sum / count

        if mean <= 5:
            if mean <= 2.5:
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
            if mean <= 7.5:
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

        reaction = random.choice(reactions)

        await client.message(
            room,
            f"DANKIES 🔔 {count:,d} chatters rated this ad segue an average of"
            f" {mean:.2f}/10 - {reaction}",
        )
