from __future__ import annotations

__all__ = [
    "IRCv3Command",
    "Privmsg",
    "Join",
    "Part",
]

import itertools
from collections.abc import Iterable, Mapping, Sequence
from typing import Final, Literal, Optional

from .parser import Parser


class IRCv3Command:

    __slots__ = (
        "_name",
        "_arguments",
        "_comment",
        "_tags",
        "_source",
    )
    __match_args__ = (
        "name",
        "arguments",
        "tags",
        "source",
    )
    _name: str
    _arguments: Sequence[str]
    _comment: Optional[str]
    _tags: Optional[Mapping[str, str]]
    _source: Optional[str]

    def __init__(
        self,
        name: str,
        arguments: Sequence[str] = (),
        comment: Optional[str] = None,
        *,
        tags: Optional[Mapping[str, str]] = None,
        source: Optional[str] = None,
    ) -> None:
        self._name = name
        self._arguments = arguments
        self._comment = comment
        self._tags = tags
        self._source = source

    def __repr__(self) -> str:
        parts = []
        name  = self._name
        parts.append("name=" + repr(name))
        if (arguments := self._arguments) is not None:
            parts.append("arguments=" + repr(arguments))
        if (comment := self._comment) is not None:
            parts.append("comment=" + repr(comment))
        if (tags := self._tags) is not None:
            parts.append("tags=" + repr(tags))
        if (source := self._source) is not None:
            parts.append("source=" + repr(source))
        return "IRCv3Command(" + ", ".join(parts) + ")"

    @property
    def name(self) -> str:
        """The command's name"""
        return self._name

    @property
    def arguments(self) -> Sequence[str]:
        """The command's arguments

        Includes the comment (or "trailing") argument if present.
        """
        arguments = []                     # Most commands have just 1-3 arguments, so
        arguments.extend(self._arguments)  # this should be fairly quick
        if (comment := self._comment) is not None:
            arguments.append(comment)
        return arguments

    @property
    def tags(self) -> Optional[Mapping[str, str]]:
        """The command's tags"""
        return self._tags

    @property
    def source(self) -> Optional[str]:
        """The command's source"""
        return self._source

    @staticmethod
    def from_string(string: str, /) -> IRCv3Command:
        """Return a new command from a raw data string"""
        parser = Parser(string)

        if parser.peek() == "@":
            tags = {
                label.removeprefix("+"): value  # TODO: Unescape values
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

        name = parser.take_until(exclude_current=False)
        arguments = parser.take_until(target=" :", exclude_current=False).split()

        if parser.ok():
            comment = parser.advance().take_all()
        else:
            comment = None

        return IRCv3Command(
            name=name,
            arguments=arguments,
            comment=comment,
            tags=tags,
            source=source,
        )

    def to_string(self) -> str:
        """Return the command as a raw data string"""
        parts = []
        if (tags := self._tags) is not None:
            parts.append("@" + ";".join(itertools.starmap(lambda label, value: f"{label}={value}", tags.items())))
        if (source := self._source) is not None:
            parts.append(":" + source)
        parts.append(self._name)
        parts.extend(self._arguments)
        if (comment := self._comment) is not None:
            parts.append(":" + comment)
        return " ".join(parts)

    __str__ = to_string


class Privmsg(IRCv3Command):

    __slots__ = ()
    _name: Final[Literal["PRIVMSG"]] = "PRIVMSG"
    _comment: str

    def __init__(self, channels: Iterable[str], comment: str, *, tags: Optional[Mapping[str, str]] = None, source: Optional[str] = None) -> None:
        arguments = []
        arguments.append(",".join(channels))
        super().__init__(self._name, arguments, comment, tags=tags, source=source)

    def __repr__(self) -> str:
        parts = []
        channels = self._arguments[0].split(",")
        parts.append("channels=" + repr(channels))
        comment = self._comment
        parts.append("comment=" + repr(comment))
        if (tags := self._tags) is not None:
            parts.append("tags=" + repr(tags))
        if (source := self._source) is not None:
            parts.append("source=" + repr(source))
        return "Privmsg(" + ", ".join(parts) + ")"

    @property
    def name(self) -> Literal["PRIVMSG"]:
        return self._name


class Join(IRCv3Command):

    __slots__ = ()
    _name: Final[Literal["JOIN"]] = "JOIN"
    _comment: Final[None] = None

    def __init__(self, channels: Iterable[str], keys: Optional[Iterable[str]] = None, *, tags: Optional[Mapping[str, str]] = None, source: Optional[str] = None) -> None:
        arguments = []
        arguments.append(",".join(channels))
        if keys is not None:
            arguments.append(",".join(keys))
        super().__init__(self._name, arguments, self._comment, tags=tags, source=source)

    def __repr__(self) -> str:
        parts = []
        arguments = self._arguments
        channels = arguments[0].split(",")
        parts.append("channels=" + repr(channels))
        if len(arguments) == 2:
            keys = arguments[1].split(",")
            parts.append("keys=" + repr(keys))
        if (tags := self._tags) is not None:
            parts.append("tags=" + repr(tags))
        if (source := self._source) is not None:
            parts.append("source=" + repr(source))
        return "Join(" + ", ".join(parts) + ")"

    @property
    def name(self) -> Literal["JOIN"]:
        return self._name


class Part(IRCv3Command):

    __slots__ = ()
    _name: Final[Literal["PART"]] = "PART"

    def __init__(self, channels: Iterable[str], reason: Optional[str] = None, *, tags: Optional[Mapping[str, str]] = None, source: Optional[str] = None) -> None:
        arguments = []
        arguments.append(",".join(channels))
        super().__init__(self._name, arguments, reason, tags=tags, source=source)

    def __repr__(self) -> str:
        parts = []
        channels = self._arguments[0].split(",")
        parts.append("channels=" + repr(channels))
        if (reason := self._comment) is not None:
            parts.append("reason=" + repr(reason))
        if (tags := self._tags) is not None:
            parts.append("tags=" + repr(tags))
        if (source := self._source) is not None:
            parts.append("source=" + repr(source))
        return "Part(" + ", ".join(parts) + ")"

    @property
    def name(self) -> Literal["PART"]:
        return self._name
