from __future__ import annotations

__all__ = ["CommandSpec"]

import itertools
from collections.abc import Iterator
from typing import NamedTuple, Self

from .param_specs import (OptionalParamSpec, ParamSpec, RequiredParamSpec,
                          VariadicParamSpec)
from .role import Role


class ParamSchema[T](NamedTuple):

    name: str
    spec: ParamSpec[T]


class RequiredParamSchema[T](NamedTuple):

    name: str
    spec: RequiredParamSpec[T]


class VariadicParamSchema[T](NamedTuple):

    name: str
    spec: VariadicParamSpec[T]


class OptionalParamSchema[T](NamedTuple):

    name: str
    spec: OptionalParamSpec[T]


class CommandSpec:
    """A collection of parameter specifications

    Represents a sort of "unnamed command", i.e., an instance of
    ``CommandSpec`` contains a command's parameters, but is not associated with
    a name (for reusability purposes).
    """

    __slots__ = (
        "role",
        "_required_schemas",
        "_variadic_schema",
        "_optional_schemas",
    )
    role: Role
    _required_schemas: dict[str, RequiredParamSpec[object]]
    _variadic_schema: VariadicParamSchema[object] | None
    _optional_schemas: dict[str, OptionalParamSpec[object]]

    def __init__(self, role: Role = Role.BROADCASTER) -> None:
        self.role = role
        self._required_schemas = {}
        self._variadic_schema = None
        self._optional_schemas = {}

    @property
    def variadic_schema(self) -> VariadicParamSchema[object] | None:
        return self._variadic_schema

    def required_schemas(self) -> Iterator[RequiredParamSchema[object]]:
        return itertools.starmap(
            RequiredParamSchema,
            self._required_schemas.items(),
        )  # type: ignore

    def optional_schemas(self) -> Iterator[OptionalParamSchema[object]]:
        return itertools.starmap(
            OptionalParamSchema,
            self._optional_schemas.items(),
        )  # type: ignore

    def get_required_spec(self, name: str) -> RequiredParamSpec[object] | None:
        return self._required_schemas.get(name)

    def get_variadic_spec(self) -> VariadicParamSpec[object] | None:
        schema = self._variadic_schema
        if schema:
            return schema.spec

    def get_optional_spec(self, name: str) -> OptionalParamSpec[object] | None:
        return self._optional_schemas.get(name)

    def add_spec(
        self,
        name: str,
        spec: ParamSpec[object] = RequiredParamSpec(),
    ) -> Self:
        """Add a parameter to the specification"""
        required_schemas = self._required_schemas
        variadic_schema = self._variadic_schema
        optional_schemas = self._optional_schemas
        if (
            name in required_schemas
            or (
                variadic_schema is not None
                and name == variadic_schema.name
            )
            or name in optional_schemas
        ):
            raise ValueError(f"Parameter name {name!r} already in use")
        if isinstance(spec, RequiredParamSpec):
            if variadic_schema:
                raise ValueError("Required parameter cannot follow a variadic parameter")
            if optional_schemas:
                raise ValueError("Required parameter cannot follow an optional parameter")
            required_schemas[name] = spec
        elif isinstance(spec, VariadicParamSpec):
            if variadic_schema:
                raise ValueError("Cannot add more than one variadic parameter")
            if optional_schemas:
                raise ValueError("Variadic parameter cannot follow an optional parameter")
            self._variadic_schema = VariadicParamSchema(
                name=name,
                spec=spec,
            )
        elif isinstance(spec, OptionalParamSpec):
            optional_schemas[name] = spec
        return self
