from __future__ import annotations

__all__ = [
    "Result",
    "Success",
    "Failure",
    "UnknownCommand",
    "BadArgument",
    "MissingArgument",
    "InconvertibleArgument",
    "CommandGroup",
]

from dataclasses import dataclass
from functools import lru_cache
from typing import Self, override

from .command_specs import CommandSpec
from .parser import Parser


@dataclass(slots=True, kw_only=True)
class Result:
    """Parsing data returned by ``CommandGroup.parse()``"""

    comment: str
    """The original comment used in parsing"""
    prefix: str
    """The command prefix used for parsing"""
    name: str
    """The name of the command used for parsing"""


@dataclass(slots=True, kw_only=True)
class Success(Result):

    parameters: dict[str, object]
    """A mapping of the command's parameters to their respective arguments, as
    specified by the ``comment``
    """


@dataclass(slots=True, kw_only=True)
class Failure(Result):

    @property
    def reason(self) -> str:
        """The reason for parsing failure

        Should be usable as a public-facing error message.
        """
        return "Unknown reason"


@dataclass(slots=True, kw_only=True)
class UnknownCommand(Failure):

    @property
    @override
    def reason(self) -> str:
        return f"Unknown command, \"{self.name}\""


@dataclass(slots=True, kw_only=True)
class BadArgument(Failure):

    parameter: str
    """The name of the parameter whose argument could not be parsed"""

    @property
    @override
    def reason(self) -> str:
        return f"Bad argument to parameter, \"{self.parameter}\""


@dataclass(slots=True, kw_only=True)
class MissingArgument(BadArgument):

    @property
    @override
    def reason(self) -> str:
        return f"Missing argument for parameter, \"{self.parameter}\""


@dataclass(slots=True, kw_only=True)
class InconvertibleArgument(BadArgument):

    argument: str
    """The argument string that could not be converted"""

    @property
    @override
    def reason(self) -> str:
        return f"Inconvertible argument, \"{self.argument}\", for parameter, \"{self.parameter}\""


class CommandGroup:
    """A collection of command specifications to parse with a common prefix

    Supports addition, removal, retrieval, and parsing of comments into command
    data.

    Note that ``CommandGroup`` instances are hashable, but should not be used
    in dictionaries and sets. Hashing is only supported for caching purposes.
    """

    __slots__ = ("prefix", "_commands", "_hash")
    prefix: str
    _commands: dict[str, CommandSpec]
    _hash: int | None

    def __init__(self, prefix: str = "!") -> None:
        self.prefix = prefix
        self._commands = {}
        self._hash = None

    def __hash__(self) -> int:
        result = self._hash
        if result is None:
            result = hash((self.prefix, tuple(self._commands.items())))
            self._hash = result
        return result

    def add_command(
        self,
        name: str,
        spec: CommandSpec = CommandSpec(),
    ) -> Self:
        """Add a command

        Raises ``ValueError`` if the command name has already been used.
        """
        commands = self._commands
        if name in commands:
            raise ValueError(f"Command name {name!r} already in use")
        commands[name] = spec
        self._hash = None  # Re-calculate hash
        return self

    def get_command(self, name: str) -> CommandSpec | None:
        """Return the command specification with the given name

        If the name has not been assigned to a specification, return ``None``.
        """
        return self._commands.get(name)

    def remove_command(self, name: str) -> bool:
        """Remove the command specification with the given name

        Returns true if a corresponding specification was found and removed,
        otherwise false.
        """
        try:
            del self._commands[name]
        except KeyError:
            return False
        else:
            self._hash = None  # Re-calculate hash
            return True

    @lru_cache()
    def parse(self, comment: str) -> Result | None:
        """Attempt to parse ``comment`` into a matching command specification

        Returns a ``Result``, which houses information about the attempt,
        depending on how far it was able to parse. See the ``Result``
        documentation and its sub-classes for more details.

        Returns ``None`` if the comment does not begin with the group's prefix.
        """
        prefix = self.prefix

        if not comment.startswith(prefix):
            return

        parser = Parser(comment, index=len(prefix))

        name = parser.take_until(exclude_current=False)
        command = self.get_command(name)

        if command is None:
            return UnknownCommand(
                comment=comment,
                prefix=prefix,
                name=name,
            )

        parameters = dict[str, object]()

        for parameter, specification in command.params():
            if parser.ok():
                argument = parser.take_until()
                try:
                    parameters[parameter] = specification.convert(argument)
                except ValueError:
                    return InconvertibleArgument(
                        comment=comment,
                        prefix=prefix,
                        name=name,
                        parameter=parameter,
                        argument=argument,
                    )
            else:
                default = specification.default
                if default is None:
                    return MissingArgument(
                        comment=comment,
                        prefix=prefix,
                        name=name,
                        parameter=parameter,
                    )
                parameters[parameter] = default

        return Success(
            comment=comment,
            prefix=prefix,
            name=name,
            parameters=parameters,
        )
