from __future__ import annotations

__all__ = [
    "Box",
    "Counter",
    "IntegerCounter",
    "DecimalCounter",
]

from dataclasses import dataclass
from decimal import Decimal


@dataclass(slots=True)
class Box[T]:
    """A wrapper around a single object, accessible through ``value``"""

    value: T


@dataclass(slots=True)
class Counter[T](Box[T]):
    """A ``Box`` type that adds a ``count``"""

    count: int = 1


@dataclass(init=False, slots=True)
class IntegerCounter(Counter[int]):
    """A ``Counter`` type whose ``value`` is an ``int``

    Adds basic arithmetic operations.
    """

    def __init__(self, value: int | str, count: int = 1) -> None:
        self.value = int(value)
        self.count = count

    def __add__(self, other: IntegerCounter) -> IntegerCounter:
        return IntegerCounter(
            self.value + other.value,
            self.count + other.count,
        )

    def __sub__(self, other: IntegerCounter) -> IntegerCounter:
        return IntegerCounter(
            self.value - other.value,
            self.count - other.count,
        )

    def __mul__(self, other: IntegerCounter) -> IntegerCounter:
        return IntegerCounter(
            self.value * other.value,
            self.count * other.count
        )


@dataclass(init=False, slots=True)
class DecimalCounter(Counter[Decimal]):
    """A ``Counter`` type whose ``value`` is a ``Decimal``

    Adds basic arithmetic operations.
    """

    def __init__(self, value: Decimal | str | float | int, count: int = 1) -> None:
        self.value = Decimal(value)
        self.count = count

    def __add__(self, other: DecimalCounter) -> DecimalCounter:
        return DecimalCounter(
            self.value + other.value,
            self.count + other.count,
        )

    def __sub__(self, other: DecimalCounter) -> DecimalCounter:
        return DecimalCounter(
            self.value - other.value,
            self.count - other.count,
        )

    def __mul__(self, other: DecimalCounter) -> DecimalCounter:
        return DecimalCounter(
            self.value * other.value,
            self.count * other.count,
        )
