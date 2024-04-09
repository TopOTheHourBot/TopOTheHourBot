from __future__ import annotations

__all__ = [
    "Match",
    "CommandGroup",
]

from dataclasses import dataclass
from typing import Self, cast

from .command_specs import CommandSpec
from .parser import Parser


@dataclass(slots=True, kw_only=True)
class Match:

    comment: str
    prefix: str
    name: str
    parameters: dict[str, object]


class CommandGroup:
    """A collection of command specifications to parse with a common prefix

    Supports addition, removal, retrieval, and parsing of comments into command
    data.
    """

    # Instantiated early since this will be the most common case by far, and
    # doesn't require string templating
    MISSING_PREFIX_ERROR = ValueError("Missing prefix")

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

    def parse(self, comment: str) -> Match | ValueError:
        """Attempt to parse ``comment`` into a matching command specification"""
        prefix = self.prefix

        if not comment.startswith(prefix):
            return self.MISSING_PREFIX_ERROR

        parser = Parser(comment, index=len(prefix))

        comm_name = parser.take_until(exclude_current=False)
        comm_spec = self.get_spec(comm_name)

        if comm_spec is None:
            return ValueError(f"Unknown command, '{comm_name}'")

        parameters = dict[str, object]()

        # Required parameters (positional only)
        for param_name, param_spec in comm_spec.required_schemas():
            if parser.ok():
                argument = parser.take_until()
                try:
                    parameters[param_name] = param_spec.factory(argument)
                except ValueError:
                    return ValueError(f"Inconvertible argument, '{argument}', provided to parameter, '{param_name}'")
            else:
                return ValueError(f"Missing argument to parameter, '{param_name}'")

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
                    return ValueError(f"Inconvertible argument, '{argument}', provided to parameter, '{param_name}'")
                else:
                    arguments = cast(list[object], parameters[param_name])
                    arguments.append(argument)

        # Optional parameters (keyword only)
        while parser.ok():
            param_name, delimiter, argument = parser.take_until().partition("=")
            param_spec = comm_spec.get_optional_spec(param_name)
            if param_spec is None:
                return ValueError(f"Unknown parameter, '{param_name}', provided to command, '{comm_name}'")
            elif delimiter:
                try:
                    parameters[param_name] = param_spec.factory(argument)
                except ValueError:
                    return ValueError(f"Inconvertible argument, '{argument}', provided to parameter, '{param_name}'")
            else:
                return ValueError(f"Missing argument to parameter, '{param_name}'")

        # Back-populate defaults for optional parameters that weren't specified
        for param_name, param_spec in comm_spec.optional_schemas():
            if param_name not in parameters:
                parameters[param_name] = param_spec.default

        return Match(
            comment=comment,
            prefix=prefix,
            name=comm_name,
            parameters=parameters,
        )
