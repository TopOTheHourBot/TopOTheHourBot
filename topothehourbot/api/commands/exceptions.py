from __future__ import annotations

__all__ = [
    "MatchError",
    "MissingPrefixError",
    "CommandError",
    "UnknownCommandError",
    "InsufficientRoleError",
    "ParameterError",
    "UnknownParameterError",
    "MissingArgumentError",
    "InconvertibleArgumentError",
]


class MatchError(ValueError):
    """Base class of the error types returned by ``CommandGroup.match()``

    Class hierarchy is as shown below. See the documentation of each for
    further details.

    ```
    ValueError
     └─ MatchError
         ├─ MissingPrefixError
         └─ CommandError
             ├─ UnknownCommandError
             ├─ InsufficientRoleError
             └─ ParameterError
                 ├─ UnknownParameterError
                 ├─ MissingArgumentError
                 └─ InconvertibleArgumentError
    ```
    """

    __slots__ = __match_args__ = ("comment", "prefix")
    comment: str
    prefix: str

    def __init__(self, *args: object, comment: str, prefix: str) -> None:
        super().__init__(*args)
        self.comment = comment
        self.prefix = prefix


class MissingPrefixError(MatchError):

    __slots__ = __match_args__ = ()

    def __init__(self, *, comment: str, prefix: str) -> None:
        super().__init__("Missing prefix", comment=comment, prefix=prefix)


class CommandError(MatchError):

    __slots__ = __match_args__ = ("command",)
    command: str

    def __init__(self, *args: object, comment: str, prefix: str, command: str) -> None:
        super().__init__(*args, comment=comment, prefix=prefix)
        self.command = command


class UnknownCommandError(CommandError):

    __slots__ = __match_args__ = ()

    def __init__(self, *, comment: str, prefix: str, command: str) -> None:
        super().__init__(
            f"Unknown command, {command}",
            comment=comment,
            prefix=prefix,
            command=command,
        )


class InsufficientRoleError(CommandError):

    __slots__ = __match_args__ = ()

    def __init__(self, comment: str, prefix: str, command: str) -> None:
        super().__init__(
            f"Sender has insufficient role to access command, '{command}'",
            comment=comment,
            prefix=prefix,
            command=command,
        )


class ParameterError(CommandError):

    __slots__ = __match_args__ = ("parameter",)
    parameter: str

    def __init__(self, *args: object, comment: str, prefix: str, command: str, parameter: str) -> None:
        super().__init__(*args, comment=comment, prefix=prefix, command=command)
        self.parameter = parameter


class UnknownParameterError(ParameterError):

    __slots__ = __match_args__ = ()

    def __init__(self, *, comment: str, prefix: str, command: str, parameter: str) -> None:
        super().__init__(
            f"Unknown parameter, '{parameter}'",
            comment=comment,
            prefix=prefix,
            command=command,
            parameter=parameter,
        )


class MissingArgumentError(ParameterError):

    __slots__ = __match_args__ = ()

    def __init__(self, *, comment: str, prefix: str, command: str, parameter: str) -> None:
        super().__init__(
            f"Missing argument to parameter, '{parameter}'",
            comment=comment,
            prefix=prefix,
            command=command,
            parameter=parameter,
        )


class InconvertibleArgumentError(ParameterError):

    __slots__ = __match_args__ = ("argument",)
    argument: str

    def __init__(self, *, comment: str, prefix: str, command: str, parameter: str, argument: str) -> None:
        super().__init__(
            f"Inconvertible argument, '{argument}', provided to parameter, '{parameter}'",
            comment=comment,
            prefix=prefix,
            command=command,
            parameter=parameter,
        )
        self.argument = argument
