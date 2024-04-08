from __future__ import annotations

__all__ = [
    "ParamSpec",
    "RequiredParamSpec",
    "VariadicParamSpec",
    "OptionalParamSpec",
]

from abc import ABCMeta, abstractmethod
from collections.abc import Callable
from typing import override


def identity[T](value: T, /) -> T:
    return value


class ParamSpec[T](metaclass=ABCMeta):
    """A parameter type and its default value"""

    __slots__ = ()

    @property
    @abstractmethod
    def factory(self) -> Callable[[str], T]:
        raise NotImplementedError


class RequiredParamSpec[T](ParamSpec[T]):

    __slots__ = ("_factory",)
    _factory: Callable[[str], T]

    def __init__(self, *, factory: Callable[[str], T] = identity) -> None:
        self._factory = factory

    @property
    @override
    def factory(self) -> Callable[[str], T]:
        return self._factory


class VariadicParamSpec[T](ParamSpec[T]):

    __slots__ = ("_factory",)
    _factory: Callable[[str], T]

    def __init__(self, *, factory: Callable[[str], T] = identity) -> None:
        self._factory = factory

    @property
    @override
    def factory(self) -> Callable[[str], T]:
        return self._factory


class OptionalParamSpec[T](ParamSpec[T]):

    __slots__ = ("_default", "_factory")
    _default: T
    _factory: Callable[[str], T]

    def __init__(self, *, default: T = "", factory: Callable[[str], T] = identity) -> None:
        self._default = default
        self._factory = factory

    @property
    @override
    def factory(self) -> Callable[[str], T]:
        return self._factory

    @property
    def default(self) -> T:
        return self._default
