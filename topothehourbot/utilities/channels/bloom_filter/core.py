from __future__ import annotations

__all__ = [
    "Status",
    "BloomFilter",
]

import enum
import math
from collections.abc import Iterator, Sized
from enum import Flag
from random import Random
from typing import Final, Generic, TypeVar

from .bits import Bits

LN2: Final[float] = 0.6931471805599453  #: Natural logarithm of 2

T_contra = TypeVar("T_contra", contravariant=True)


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


class Status(Flag):
    """Flags used to signal the result of adding a value to a bloom filter"""

    ACCEPTED = enum.auto()
    REJECTED = enum.auto()
    FULL = enum.auto()

    def __bool__(self) -> bool:
        return self is Status.ACCEPTED


class BloomFilter(Sized, Generic[T_contra]):

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

    def __contains__(self, value: T_contra, /) -> bool:
        return all(map(self._bits.__getitem__, self.seeded_indices(value)))

    @property
    def size(self) -> int:
        """The current number of elements"""
        return self._size

    @property
    def max_size(self) -> int:
        """The maximum number of elements"""
        return self._max_size

    def seeded_indices(self, value: T_contra, /) -> Iterator[int]:
        """Return an iterator of random indices, seeded by ``value``, for use
        in searching or setting filter bits
        """
        random = Random(seed(value))
        nbits = len(self._bits)
        for _ in range(self._gen_size):
            scale = random.random()
            yield int(scale * nbits)

    def full(self) -> bool:
        """Return true if the filter has reached its maximum size, otherwise
        false
        """
        return self._size >= self._max_size

    def add(self, value: T_contra, /) -> Status:
        """Add ``value`` to the filter and return a truthy object, or do
        nothing and return a falsy object if the value probably exists, or if
        the filter has reached its maximum size

        This method returns a member of the ``Status`` enum. See its
        documentation for more details.
        """
        if self.full():
            return Status.FULL
        bits = self._bits
        new = False
        for index in self.seeded_indices(value):
            if new or not bits[index]:
                new = True
                bits[index] = True
        if new:
            self._size += 1
            return Status.ACCEPTED
        return Status.REJECTED
