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
    "ArgumentError",
    "InconvertibleArgumentError",
]


class MatchError(ValueError):
    """Base class of all error types returned by ``CommandGroup.match()``

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
                 └─ ArgumentError
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
    """Message does not begin with the command group prefix"""

    __slots__ = __match_args__ = ()

    def __init__(self, *, comment: str, prefix: str) -> None:
        super().__init__(
            f"Missing command prefix, '{prefix}'",
            comment=comment,
            prefix=prefix,
        )


class CommandError(MatchError):
    """Message contains a command, but there is an issue with its call"""

    __slots__ = __match_args__ = ("command",)
    command: str

    def __init__(self, *args: object, comment: str, prefix: str, command: str) -> None:
        super().__init__(*args, comment=comment, prefix=prefix)
        self.command = command


class UnknownCommandError(CommandError):
    """Command name is unused by the command group"""

    __slots__ = __match_args__ = ()

    def __init__(self, *, comment: str, prefix: str, command: str) -> None:
        super().__init__(
            f"Unknown command, '{command}'",
            comment=comment,
            prefix=prefix,
            command=command,
        )


class InsufficientRoleError(CommandError):
    """Sender of the command does not have a sufficient role"""

    __slots__ = __match_args__ = ()

    def __init__(self, comment: str, prefix: str, command: str) -> None:
        super().__init__(
            f"Insufficient role to access command, '{command}'",
            comment=comment,
            prefix=prefix,
            command=command,
        )


class ParameterError(CommandError):
    """The command exists and is accessible to the sender, but there is an
    issue with a parameter call
    """

    __slots__ = __match_args__ = ("parameter",)
    parameter: str

    def __init__(self, *args: object, comment: str, prefix: str, command: str, parameter: str) -> None:
        super().__init__(*args, comment=comment, prefix=prefix, command=command)
        self.parameter = parameter


class UnknownParameterError(ParameterError):
    """The command call invokes a parameter that does not exist"""

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
    """The command call does not provide an argument to a required parameter"""

    __slots__ = __match_args__ = ()

    def __init__(self, *, comment: str, prefix: str, command: str, parameter: str) -> None:
        super().__init__(
            f"Missing argument to parameter, '{parameter}'",
            comment=comment,
            prefix=prefix,
            command=command,
            parameter=parameter,
        )


class ArgumentError(ParameterError):
    """The command exists, is accessible to the sender, and the call is
    parametrically correct, but there is an issue with a given argument
    """

    __slots__ = __match_args__ = ("argument",)
    argument: str

    def __init__(self, *args: object, comment: str, prefix: str, command: str, parameter: str, argument: str) -> None:
        super().__init__(*args, comment=comment, prefix=prefix, command=command, parameter=parameter)
        self.argument = argument


class InconvertibleArgumentError(ArgumentError):
    """The argument cannot be converted to the parameter's expected type"""

    __slots__ = __match_args__ = ()

    def __init__(self, *, comment: str, prefix: str, command: str, parameter: str, argument: str) -> None:
        super().__init__(
            f"Inconvertible argument, '{argument}', provided to parameter, '{parameter}'",
            comment=comment,
            prefix=prefix,
            command=command,
            parameter=parameter,
            argument=argument,
        )
