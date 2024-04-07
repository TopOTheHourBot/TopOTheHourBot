from __future__ import annotations

__all__ = [
    "ParamSpec",
    "InstancedDefaultParamSpec",
    "StringParamSpec",
    "IntegerParamSpec",
    "FloatParamSpec",
    "HandleParamSpec",
]

from abc import ABCMeta, abstractmethod
from typing import override


class ParamSpec[T](metaclass=ABCMeta):
    """A parameter type and its default value"""

    __slots__ = ()

    def __hash__(self) -> int:
        return hash(self.default)

    @property
    @abstractmethod
    def default(self) -> T | None:
        """An argument to use when the parameter has not been invoked

        Set to ``None`` if the parameter has no default (a required parameter).
        This object should be inexpensive to compute.
        """
        raise NotImplementedError

    @abstractmethod
    def convert(self, argument: str, /) -> T:
        """Try to convert an argument to the desired type

        If inconvertible, raise ``ValueError``.
        """
        raise NotImplementedError

    def required(self) -> bool:
        """Return true if the ``default`` is ``None``, otherwise false"""
        return self.default is None

    def optional(self) -> bool:
        """Return true if the ``default`` is not ``None``, otherwise false"""
        return self.default is not None


class InstancedDefaultParamSpec[T](ParamSpec[T], metaclass=ABCMeta):
    """A type of ``ParamSpec`` whose ``default`` is stored as an instance
    attribute
    """

    __slots__ = ("_default",)
    _default: T | None

    def __init__(self, default: T | None = None) -> None:
        self._default = default

    @property
    @override
    def default(self) -> T | None:
        return self._default


class StringParamSpec(InstancedDefaultParamSpec[str]):

    __slots__ = ()

    @override
    def convert(self, argument: str, /) -> str:
        return argument


class IntegerParamSpec(InstancedDefaultParamSpec[int]):

    __slots__ = ()

    @override
    def convert(self, argument: str, /) -> int:
        return int(argument)


class FloatParamSpec(InstancedDefaultParamSpec[float]):

    __slots__ = ()

    @override
    def convert(self, argument: str, /) -> float:
        return float(argument)


class HandleParamSpec(StringParamSpec):

    __slots__ = ()

    @override
    def convert(self, argument: str) -> str:
        return "@" + super().convert(argument).lstrip("@")
