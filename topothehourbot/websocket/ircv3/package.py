from __future__ import annotations

import itertools
from collections.abc import Mapping, Sequence
from typing import Optional, Self

from .parser import Parser

__all__ = ["IRCv3Package"]


class IRCv3Package:

    __slots__ = (
        "_command",
        "_arguments",
        "_comment",
        "_tags",
        "_source",
    )
    __match_args__ = (
        "command",
        "arguments",
        "tags",
        "source",
    )

    _command: str
    _arguments: Sequence[str]
    _comment: Optional[str]
    _tags: Optional[Mapping[str, str]]
    _source: Optional[str]

    def __init__(
        self,
        command: str,
        arguments: Sequence[str] = (),
        comment: Optional[str] = None,
        *,
        tags: Optional[Mapping[str, str]] = None,
        source: Optional[str] = None,
    ) -> None:
        self._command = command
        self._arguments = arguments
        self._comment = comment
        self._tags = tags
        self._source = source

    def __repr__(self) -> str:
        return "IRCv3Package(command={}, arguments={}, comment={}, tags={}, source={})".format(
            self._command,
            self._arguments,
            self._comment,
            self._tags,
            self._source,
        )

    def __str__(self) -> str:
        parts = []
        if (tags := self._tags):
            parts.append("@" + ";".join(itertools.starmap(lambda label, value: f"{label}={value}", tags.items())))
        if (source := self._source):
            parts.append(":" + source)
        parts.append(self._command)
        parts.extend(self._arguments)
        if (comment := self._comment) is not None:
            parts.append(":" + comment)
        return " ".join(parts)

    @property
    def command(self) -> str:
        """The package's command"""
        return self._command

    @property
    def arguments(self) -> Sequence[str]:
        """The package's command arguments

        Includes the comment (or "trailing") argument if present.
        """
        arguments = []
        arguments.extend(self._arguments)
        if (comment := self._comment) is not None:
            arguments.append(comment)
        return arguments

    @property
    def tags(self) -> Optional[Mapping[str, str]]:
        """The package tags"""
        return self._tags

    @property
    def source(self) -> Optional[str]:
        """The package source"""
        return self._source

    @classmethod
    def from_string(cls, string: str, /) -> Self:
        """Return a new package from a raw data string"""
        parser = Parser(string)

        if parser.peek() == "@":
            tags = {
                label.removeprefix("+"): value  # TODO: unescape values
                for label, _, value in map(
                    lambda tag: tag.partition("="),
                    parser.take_until().split(";"),
                )
            }
            parser.advance()
        else:
            tags = None

        if parser.peek() == ":":
            source = parser.take_until()
            parser.advance()
        else:
            source = None

        command   = parser.take_until(exclude_current=False)
        arguments = parser.take_until(target=" :", exclude_current=False).split()

        if parser.ok():
            comment = parser.advance().take_all()
        else:
            comment = None

        return cls(
            command=command,
            arguments=arguments,
            comment=comment,
            tags=tags,
            source=source,
        )
