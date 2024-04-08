from __future__ import annotations

__all__ = ["CommandSpec"]

import itertools
from collections.abc import Iterator
from typing import Self

from .param_specs import ParamSpec, StringParamSpec


class CommandSpec:
    """A collection of parameter specifications

    Represents a sort of "unnamed command", i.e., an instance of
    ``CommandSpec`` contains a command's parameters, but is not associated with
    a name (for reusability purposes).

    Note that ``CommandSpec`` instances are hashable, but should not be used in
    dictionaries and sets. Hashing is only supported for caching purposes.
    """

    __slots__ = ("_required_params", "_optional_params", "_hash")
    _required_params: dict[str, ParamSpec[object]]
    _optional_params: dict[str, ParamSpec[object]]
    _hash: int | None

    def __init__(self) -> None:
        self._required_params = {}
        self._optional_params = {}
        self._hash = None

    def __hash__(self) -> int:
        result = self._hash
        if result is None:
            result = hash(
                (
                    tuple(self.required_params()),
                    tuple(self.optional_params()),
                ),
            )
            self._hash = result
        return result

    def params(self) -> Iterator[tuple[str, ParamSpec[object]]]:
        return itertools.chain(self.required_params(), self.optional_params())

    def required_params(self) -> Iterator[tuple[str, ParamSpec[object]]]:
        """Return an iterator over the specification's required parameters"""
        return iter(self._required_params.items())

    def optional_params(self) -> Iterator[tuple[str, ParamSpec[object]]]:
        """Return an iterator over the specification's optional parameters"""
        return iter(self._optional_params.items())

    def get_required_param(self, name: str) -> ParamSpec[object] | None:
        return self._required_params.get(name, None)

    def get_optional_param(self, name: str) -> ParamSpec[object] | None:
        return self._optional_params.get(name, None)

    def add_param(
        self,
        name: str,
        spec: ParamSpec[object] = StringParamSpec(),
    ) -> Self:
        """Add a parameter to the specification

        Raises ``ValueError`` if the parameter name has already been used, or
        if the specification has no default while prior ones do.
        """
        if self.get_required_param(name) or self.get_optional_param(name):
            raise ValueError(f"Parameter name {name!r} already in use")
        if spec.required() and self._optional_params:
            raise ValueError("Required parameter cannot follow an optional parameter")
        if spec.required():
            self._required_params[name] = spec
        else:
            self._optional_params[name] = spec
        self._hash = None  # Re-calculate hash
        return self
