from __future__ import annotations

__all__ = [
    "CapacityError",
    "BloomFilter",
]

import math
from collections.abc import Iterator
from random import Random
from typing import Final, Generic, TypeVar

from .bits import Bits

LN2: Final[float] = 0.6931471805599453  #: Natural logarithm of 2

T = TypeVar("T")


def seed(obj: object, /) -> int:
    """Return a seed unique to ``obj`` for use in random number generation

    Special behavior is employed for certain built-in types. User-defined types
    will commonly have their ``__hash__()`` implementation called upon.
    """

    # We don't use an instance check because it's possible to have user-defined
    # subclasses with other data

    obj_type = type(obj)
    if obj_type is int:
        return obj  # type: ignore
    if obj_type in {bytes, bytearray}:
        return int.from_bytes(obj)  # type: ignore
    if obj_type is str:
        return int.from_bytes(obj.encode())  # type: ignore
    return hash(obj)


class CapacityError(Exception):
    """Collection has reached a capacity"""

    __slots__ = ()


class BloomFilter(Generic[T]):

    __slots__ = ("_size", "_max_size", "_gen_size", "_bits")
    _size: int
    _max_size: int
    _gen_size: int
    _bits: Bits

    def __init__(self, max_size: int, error: float = 0.01) -> None:
        max_size = max(max_size, 0)
        if __debug__:
            if not (0 < error <= 1):
                raise ValueError("error must be a value between 0 and 1")

        m = math.ceil((-max_size * math.log(error)) / (LN2 * LN2))
        k = math.ceil((LN2 * m) / max_size)

        self._size = 0
        self._max_size = max_size
        self._gen_size = k
        self._bits = Bits.zeros(m)

    def __len__(self) -> int:
        return self._size

    def __contains__(self, value: T, /) -> bool:
        return all(map(self._bits.__getitem__, self.seed_indices(value)))

    @property
    def size(self) -> int:
        """The current number of elements"""
        return self._size

    @property
    def max_size(self) -> int:
        """The maximum number of elements"""
        return self._max_size

    def seed_indices(self, value: T, /) -> Iterator[int]:
        random = Random(seed(value))
        nbits = len(self._bits)
        for _ in range(self._gen_size):
            scale = random.random()
            yield int(scale * nbits)

    def add(self, value: T, /) -> bool:
        """Add ``value`` to the filter, or do nothing if it already exists

        Returns true if the value was added, otherwise false.

        Raises ``CapacityError`` if the filter has reached its ``max_size``.
        """
        size = self._size
        if size == self._max_size:
            raise CapacityError("filter has reached its capacity")
        bits = self._bits
        dupe = True
        for index in self.seed_indices(value):
            if (not dupe) or (not bits[index]):
                dupe = False
                bits[index] = True
        result = not dupe
        self._size = size + result
        return result
