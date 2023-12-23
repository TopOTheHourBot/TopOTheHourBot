from __future__ import annotations

__all__ = [
    "Box",
    "Counter",
    "IntegerCounter",
    "RealCounter",
]

from dataclasses import dataclass


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
class RealCounter(Counter[float]):
    """A ``Counter`` type whose ``value`` is a ``float``

    Adds basic arithmetic operations.
    """

    def __init__(self, value: float | int | str, count: int = 1) -> None:
        self.value = float(value)
        self.count = count

    def __add__(self, other: RealCounter) -> RealCounter:
        return RealCounter(
            self.value + other.value,
            self.count + other.count,
        )

    def __sub__(self, other: RealCounter) -> RealCounter:
        return RealCounter(
            self.value - other.value,
            self.count - other.count,
        )

    def __mul__(self, other: RealCounter) -> RealCounter:
        return RealCounter(
            self.value * other.value,
            self.count * other.count,
        )

    def clamp(self, lower: float, upper: float) -> RealCounter:
        """Return a new ``RealCounter`` with ``value`` clamped between
        ``lower`` and ``upper``
        """
        return RealCounter(
            max(lower, min(upper, self.value)),
            self.count,
        )
