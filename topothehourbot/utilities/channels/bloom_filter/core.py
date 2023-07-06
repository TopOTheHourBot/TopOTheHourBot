from __future__ import annotations

__all__ = [
    "SupportsSeed",
    "seed",
    "Status",
    "BloomFilter",
]

import enum
import math
from collections.abc import Iterable, Iterator, Sized
from enum import Flag
from random import Random
from typing import Final, Generic, Protocol, TypeVar, runtime_checkable

from .bits import Bits

LN2: Final[float] = 0.6931471805599453  #: Natural logarithm of 2

T_contra = TypeVar("T_contra", contravariant=True)


@runtime_checkable
class SupportsSeed(Protocol):

    def seed(self) -> int:
        """Return a seed unique to the object

        Can be implemented in a similar fashion to built-in ``__hash__()``, but
        the type does not have to be immutable.

        Acts as an alias for ``__hash__()`` by default.
        """
        return hash(self)


def seed(obj: object, /) -> int:
    """Return a seed unique to ``obj`` for use in random number generation

    Special behavior is employed for certain built-in types. User-defined types
    can explicitly or implicitly support seeding by implementing the
    ``SupportsSeed`` protocol, or the built-in ``__hash__()`` method,
    respectively.
    """
    obj_type = type(obj)
    if obj_type is int:
        return obj  # type: ignore
    if obj_type in {bytes, bytearray}:
        return int.from_bytes(obj)  # type: ignore
    if obj_type is str:
        return int.from_bytes(obj.encode())  # type: ignore
    try:
        return obj.seed()  # type: ignore
    except AttributeError:
        pass
    try:
        return hash(obj)
    except TypeError:
        pass
    raise TypeError(f"cannot create seed from object of type {obj_type.__name__!r}")


class Status(Flag):
    """Flags used to signal the result of adding a value to a bloom filter"""

    ACCEPTED = enum.auto()  #: Value was added to the filter
    REJECTED = enum.auto()  #: Value was not added to the filter
    FULL     = enum.auto()  #: Filter has reached its capacity

    def __bool__(self) -> bool:
        return self is Status.ACCEPTED


class BloomFilter(Sized, Generic[T_contra]):
    """A basic bloom filter

    Supports objects of any type that implements ``__hash__()``. Fast-paths are
    employed for certain built-in types.

    The indices into the underlying bit array are generated via the built-in
    ``random.Random`` class, where the object's hash is used as its seed.

    If the number of values exceeds ``max_size``, values from that time onwards
    are left unwritten to the filter, which may create false negatives. It's,
    thus, best practice to overestimate ``max_size``, as it doesn't incur much
    additional memory.

    Filtering on a union type is ill-advised, as the ``__hash__()`` method does
    not encode a notion of class (and can therefore produce identical hashes to
    those of a different type, possibly within the same union).
    """

    __slots__ = ("_size", "_max_size", "_gen_size", "_bits")
    _size: int
    _max_size: int
    _gen_size: int
    _bits: Bits

    def __init__(self, values: Iterable[T_contra] = (), /, *, max_size: int = 256, error: float = 0.01) -> None:
        if __debug__:
            if not (0 < error <= 1):
                raise ValueError("error must be a value greater than 0, and less than or equal to 1")

        if max_size <= 0:
            m = k = 0
        else:
            m = math.ceil((-max_size * math.log(error)) / (LN2 * LN2))
            k = math.ceil((m / max_size) * LN2)

        self._size = 0
        self._max_size = max_size
        self._gen_size = k
        self._bits = Bits.zeros(m)

        for value in values:
            self.add(value)

    def __len__(self) -> int:
        return self._size

    def __contains__(self, value: T_contra, /) -> bool:
        return all(map(self._bits.__getitem__, self._seed_indices(value)))

    def _seed_indices(self, value: T_contra, /) -> Iterator[int]:
        random = Random(seed(value))
        n = len(self._bits)
        for _ in range(self._gen_size):
            scale = random.random()
            yield int(scale * n)

    @property
    def size(self) -> int:
        """The current number of elements"""
        return self._size

    @property
    def max_size(self) -> int:
        """The maximum number of elements"""
        return self._max_size

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

        bits    = self._bits
        indices = self._seed_indices(value)

        zero_index = None
        for index in indices:
            if not bits[index]:
                zero_index = index
                break
        if zero_index is None:
            return Status.REJECTED

        bits[zero_index] = True
        for index in indices:
            bits[index] = True

        self._size += 1

        return Status.ACCEPTED
