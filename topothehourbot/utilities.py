from __future__ import annotations

__all__ = ["Rating"]

import re
from decimal import Decimal
from re import Pattern
from typing import ClassVar, Self

from ircv3.twitch import ServerMessage


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
        return cls(
            message,
            value=Decimal(match.group(1)),
            index_begin=match.span(1)[0],
            index_end=match.span(1)[1],
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
