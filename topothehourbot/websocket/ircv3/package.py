from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Optional, Self, overload

from .parser import Parser

__all__ = ["IRCv3Package"]


class IRCv3Package(Sequence[str]):

    __slots__ = __match_args__ = (
        "command",
        "arguments",
        "tags",
        "source",
    )

    command: str
    arguments: Sequence[str]
    tags: Optional[Mapping[str, str]]
    source: Optional[str]

    def __init__(self, command: str, arguments: Sequence[str] = (), *, tags: Optional[Mapping[str, str]] = None, source: Optional[str] = None) -> None:
        self.command = command
        self.arguments = arguments
        self.tags = tags
        self.source = source

    def __repr__(self) -> str:
        return f"IRCv3Package(command={self.command!r}, arguments={self.arguments!r}, tags={self.tags!r}, source={self.source!r})"

    def __len__(self) -> int:
        return len(self.arguments)

    @overload
    def __getitem__(self, key: int) -> str: ...
    @overload
    def __getitem__(self, key: slice) -> Sequence[str]: ...

    def __getitem__(self, key: slice | int) -> Sequence[str] | str:
        return self.arguments[key]

    @classmethod
    def from_string(cls, string: str, /) -> Self:
        """Return a new ``IRCv3Package`` by destructuring a raw IRCv3-compatible
        string
        """
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
            trailing_argument = parser.advance().take_all()
            arguments.append(trailing_argument)

        return cls(
            command=command,
            arguments=arguments,
            tags=tags,
            source=source,
        )
