from __future__ import annotations

__all__ = [
    "Match",
    "CommandGroup",
]

from dataclasses import dataclass
from typing import Self, cast

from ircv3.dialects.twitch import ServerMessage

from .command_specs import CommandSpec
from .exceptions import (InconvertibleArgumentError, InsufficientRoleError,
                         MatchError, MissingArgumentError, MissingPrefixError,
                         UnknownCommandError, UnknownParameterError)
from .parser import Parser
from .role import Role


@dataclass(slots=True, kw_only=True)
class Match:

    comment: str
    prefix: str
    command: str
    parameters: dict[str, object]


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

    def match(self, message: ServerMessage) -> Match | MatchError:
        """Attempt to parse ``message`` into a matching command specification"""
        prefix = self.prefix
        comment = message.comment

        if not comment.startswith(prefix):
            return MissingPrefixError(
                comment=comment,
                prefix=prefix,
            )

        parser = Parser(comment, index=len(prefix))

        comm_name = parser.take_until(exclude_current=False)
        comm_spec = self.get_spec(comm_name)

        if comm_spec is None:
            return UnknownCommandError(
                comment=comment,
                prefix=prefix,
                command=comm_name,
            )
        if Role.from_client(message.sender) < comm_spec.role:
            return InsufficientRoleError(
                comment=comment,
                prefix=prefix,
                command=comm_name,
            )

        parameters = dict[str, object]()

        # Required parameters (positional only)
        for param_name, param_spec in comm_spec.required_schemas():
            if parser.ok():
                argument = parser.take_until()
                try:
                    parameters[param_name] = param_spec.factory(argument)
                except ValueError:
                    return InconvertibleArgumentError(
                        comment=comment,
                        prefix=prefix,
                        command=comm_name,
                        parameter=param_name,
                        argument=argument,
                    )
            else:
                return MissingArgumentError(
                    comment=comment,
                    prefix=prefix,
                    command=comm_name,
                    parameter=param_name,
                )

        # Variadic parameter
        variadic_schema = comm_spec.variadic_schema
        if variadic_schema:
            param_name, param_spec = variadic_schema
            parameters[param_name] = []
            while parser.ok():
                argument = parser.take_until()
                if "=" in argument:
                    # Presence of the equals sign indicates that this is an
                    # optional parameter - put the parser back to the beginning
                    # of this token and let the optional-parameter-parsing code
                    # take it from here
                    parser.advance(-len(argument) - 1)
                    break
                try:
                    argument = param_spec.factory(argument)
                except ValueError:
                    return InconvertibleArgumentError(
                        comment=comment,
                        prefix=prefix,
                        command=comm_name,
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
                return UnknownParameterError(
                    comment=comment,
                    prefix=prefix,
                    command=comm_name,
                    parameter=param_name,
                )
            elif delimiter:
                try:
                    parameters[param_name] = param_spec.factory(argument)
                except ValueError:
                    return InconvertibleArgumentError(
                        comment=comment,
                        prefix=prefix,
                        command=comm_name,
                        parameter=param_name,
                        argument=argument,
                    )
            else:
                # This case occurs when we're given an invocation alike:
                # `!command optional_param_name`
                # I experimented with inferring the default in this scenario
                # but it's a bit too confusing in my opinion
                return MissingArgumentError(
                    comment=comment,
                    prefix=prefix,
                    command=comm_name,
                    parameter=param_name,
                )

        # Back-populate defaults for optional parameters that weren't specified
        for param_name, param_spec in comm_spec.optional_schemas():
            if param_name not in parameters:
                parameters[param_name] = param_spec.default

        return Match(
            comment=comment,
            prefix=prefix,
            command=comm_name,
            parameters=parameters,
        )

    def match_raise(self, message: ServerMessage) -> Match:
        result = self.match(message)
        if isinstance(result, MatchError):
            raise result
        return result
