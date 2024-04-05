from __future__ import annotations

__all__ = ["CommandSpec"]

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

    __slots__ = ("_params", "_hash")
    _params: dict[str, ParamSpec[object]]
    _hash: int | None

    def __init__(self) -> None:
        self._params = {}
        self._hash = None

    def __hash__(self) -> int:
        result = self._hash
        if result is None:
            result = hash(tuple(self._params.items()))
            self._hash = result
        return result

    def params(self) -> Iterator[tuple[str, ParamSpec[object]]]:
        """Return an iterator over the specification's parameter names and
        specifications
        """
        return iter(self._params.items())

    def add_param(
        self,
        name: str,
        spec: ParamSpec[object] = StringParamSpec(),
    ) -> Self:
        """Add a parameter to the specification

        Raises ``ValueError`` if the parameter name has already been used, or
        if the specification has no default while prior ones do.
        """
        params = self._params
        if name in params:
            raise ValueError(f"Parameter name {name!r} already in use")
        if spec.required() and params:
            prior_spec = next(reversed(params.values()))
            if prior_spec.optional():
                raise ValueError("Non-defaulting parameter cannot follow a defaulting parameter")
        params[name] = spec
        self._hash = None  # Re-calculate hash
        return self
