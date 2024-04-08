from __future__ import annotations

__all__ = [
    "Result",
    "Success",
    "Failure",
    "UnknownCommand",
    "UnknownParameter",
    "BadArgument",
    "MissingArgument",
    "InconvertibleArgument",
    "CommandGroup",
]

from dataclasses import dataclass
from typing import Self, cast, override

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
class UnknownParameter(Failure):

    parameter: str
    """The name of the unknown parameter"""

    @property
    @override
    def reason(self) -> str:
        return f"Unknown parameter, \"{self.parameter}\""


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
    """

    __slots__ = ("prefix", "_schemas")
    prefix: str
    _schemas: dict[str, CommandSpec]

    def __init__(self, prefix: str = "!") -> None:
        self.prefix = prefix
        self._schemas = {}

    def add_spec(
        self,
        name: str,
        spec: CommandSpec = CommandSpec(),
    ) -> Self:
        """Add a command

        Raises ``ValueError`` if the command name has already been used.
        """
        schemas = self._schemas
        if name in schemas:
            raise ValueError(f"Command name {name!r} already in use")
        schemas[name] = spec
        return self

    def get_spec(self, name: str) -> CommandSpec | None:
        """Return the command specification with the given name

        If the name has not been assigned to a specification, return ``None``.
        """
        return self._schemas.get(name)

    def remove_spec(self, name: str) -> bool:
        """Remove the command specification with the given name

        Returns true if a corresponding specification was found and removed,
        otherwise false.
        """
        try:
            del self._schemas[name]
        except KeyError:
            return False
        else:
            return True

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

        comm_name = parser.take_until(exclude_current=False)
        comm_spec = self.get_spec(comm_name)

        if comm_spec is None:
            return UnknownCommand(
                comment=comment,
                prefix=prefix,
                name=comm_name,
            )

        parameters = dict[str, object]()

        # Required parameters (positional only)
        for param_name, param_spec in comm_spec.required_schemas():
            if parser.ok():
                argument = parser.take_until()
                try:
                    parameters[param_name] = param_spec.factory(argument)
                except ValueError:
                    return InconvertibleArgument(
                        comment=comment,
                        prefix=prefix,
                        name=comm_name,
                        parameter=param_name,
                        argument=argument,
                    )
            else:
                return MissingArgument(
                    comment=comment,
                    prefix=prefix,
                    name=comm_name,
                    parameter=param_name,
                )

        # Variadic parameter
        variadic_schema = comm_spec.variadic_schema()
        if variadic_schema:
            param_name, param_spec = variadic_schema
            parameters[param_name] = []
            while parser.ok():
                argument = parser.take_until()
                if "=" in argument:
                    parser.advance(-len(argument) - 1)
                    break
                try:
                    argument = param_spec.factory(argument)
                except ValueError:
                    return InconvertibleArgument(
                        comment=comment,
                        prefix=prefix,
                        name=comm_name,
                        parameter=param_name,
                        argument=argument,
                    )
                else:
                    arguments = cast(list[object], parameters[param_name])
                    arguments.append(argument)

        # Optional parameters (keyword only)
        while parser.ok():
            param_name, delimiter, argument = parser.take_until().partition("=")
            param_spec = comm_spec.get_optional_spec(param_name)
            if param_spec is None:
                return UnknownParameter(
                    comment=comment,
                    prefix=prefix,
                    name=comm_name,
                    parameter=param_name,
                )
            elif delimiter:
                try:
                    parameters[param_name] = param_spec.factory(argument)
                except ValueError:
                    return InconvertibleArgument(
                        comment=comment,
                        prefix=prefix,
                        name=comm_name,
                        parameter=param_name,
                        argument=argument,
                    )
            else:
                return MissingArgument(
                    comment=comment,
                    prefix=prefix,
                    name=comm_name,
                    parameter=param_name,
                )

        # Back-populate defaults for optional parameters that weren't specified
        for param_name, param_spec in comm_spec.optional_schemas():
            if param_name not in parameters:
                parameters[param_name] = param_spec.default

        return Success(
            comment=comment,
            prefix=prefix,
            name=comm_name,
            parameters=parameters,
        )
