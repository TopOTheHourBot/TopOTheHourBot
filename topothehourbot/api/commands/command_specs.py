from __future__ import annotations

__all__ = ["CommandSpec"]

from collections.abc import Iterator
from typing import Self

from .param_specs import (OptionalParamSpec, ParamSpec, RequiredParamSpec,
                          VariadicParamSpec)

type ParamSchema[T] = tuple[str, ParamSpec[T]]
type RequiredParamSchema[T] = tuple[str, RequiredParamSpec[T]]
type VariadicParamSchema[T] = tuple[str, VariadicParamSpec[T]]
type OptionalParamSchema[T] = tuple[str, OptionalParamSpec[T]]


class CommandSpec:
    """A collection of parameter specifications

    Represents a sort of "unnamed command", i.e., an instance of
    ``CommandSpec`` contains a command's parameters, but is not associated with
    a name (for reusability purposes).
    """

    __slots__ = (
        "_required_schemas",
        "_variadic_schema",
        "_optional_schemas",
    )
    _required_schemas: dict[str, RequiredParamSpec[object]]
    _variadic_schema: VariadicParamSchema[object] | None
    _optional_schemas: dict[str, OptionalParamSpec[object]]

    def __init__(self) -> None:
        self._required_schemas = {}
        self._variadic_schema = None
        self._optional_schemas = {}

    def schemas(self) -> Iterator[ParamSchema[object]]:
        yield from self.required_schemas()
        schema = self.variadic_schema()
        if schema is not None:
            yield schema
        yield from self.optional_schemas()

    def required_schemas(self) -> Iterator[RequiredParamSchema[object]]:
        return iter(self._required_schemas.items())

    def variadic_schema(self) -> VariadicParamSchema[object] | None:
        return self._variadic_schema

    def optional_schemas(self) -> Iterator[OptionalParamSchema[object]]:
        return iter(self._optional_schemas.items())

    def get_required_spec(self, name: str) -> RequiredParamSpec[object] | None:
        return self._required_schemas.get(name, None)

    def get_variadic_spec(self) -> VariadicParamSpec[object] | None:
        schema = self._variadic_schema
        if schema:
            return schema[1]

    def get_optional_spec(self, name: str) -> OptionalParamSpec[object] | None:
        return self._optional_schemas.get(name, None)

    def add_spec(
        self,
        name: str,
        spec: ParamSpec[object] = RequiredParamSpec(),
    ) -> Self:
        """Add a parameter to the specification"""
        variadic_schema = self._variadic_schema
        if variadic_schema and name == variadic_schema[0]:
            raise ValueError(f"Parameter name {name!r} already in use")
        required_schemas = self._required_schemas
        optional_schemas = self._optional_schemas
        if required_schemas.get(name) or optional_schemas.get(name):
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
            self._variadic_schema = (name, spec)
        elif isinstance(spec, OptionalParamSpec):
            optional_schemas[name] = spec
        return self
