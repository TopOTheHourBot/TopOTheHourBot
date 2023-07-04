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

ln2: Final[float] = 0.6931471805599453  #: Natural logarithm of 2

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

    __slots__ = ("_size", "_max_size", "_gen_count", "_bits")
    _size: int
    _max_size: int
    _gen_count: int
    _bits: Bits

    def __init__(self, max_size: int, error: float = 0.01) -> None:
        max_size = max(max_size, 0)
        if __debug__:
            if not (0 < error <= 1):
                raise ValueError("error must be a value between 0 and 1")

        # See here for calculations:
        # https://en.wikipedia.org/wiki/Bloom_filter#Optimal_number_of_hash_functions

        m = math.ceil((-max_size * math.log(error)) / (ln2 * ln2))
        k = math.ceil((ln2 * m) / max_size)

        self._size = 0
        self._max_size = max_size
        self._gen_count = k
        self._bits = Bits.zeros(m)

    def __len__(self) -> int:
        return self._size

    def __contains__(self, value: T, /) -> bool:
        return all(map(self._bits.__getitem__, self.indices(value)))

    @property
    def size(self) -> int:
        return self._size

    @property
    def max_size(self) -> int:
        return self._max_size

    def indices(self, value: T, /) -> Iterator[int]:
        randomizer = Random(seed(value))
        bit_count = len(self._bits)
        gen_count = self._gen_count
        for _ in range(gen_count):
            scale = randomizer.random()
            yield int(scale * bit_count)

    def add(self, value: T, /) -> None:
        size = self._size
        if size == self._max_size:
            raise CapacityError("filter has reached its capacity")
        bits = self._bits
        for index in self.indices(value):
            bits[index] = True
        self._size = size + 1
