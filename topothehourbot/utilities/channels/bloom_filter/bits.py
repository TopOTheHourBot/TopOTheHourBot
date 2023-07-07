from __future__ import annotations

__all__ = [
    "BYTE_SIZE",
    "Bit",
    "Bits",
]

import itertools
import operator
from collections.abc import Iterable, Iterator, Sequence
from typing import (Final, Literal, Optional, Self, SupportsIndex, TypeAlias,
                    overload)

BYTE_SIZE: Final[Literal[8]] = 8  #: The number of bits in a single byte

Bit: TypeAlias = Literal[0, 1]  #: Literal 0 and 1


def resolve_index(key: SupportsIndex, bound: int) -> int:
    """Return ``key`` as an index with respect to ``bound``

    Raises an empty ``IndexError`` if ``key`` is out of range.
    """
    index = operator.index(key)
    if index < 0:
        index += bound
    if index < 0 or index >= bound:
        raise IndexError
    return index


def resolve_slice(key: slice, bound: int) -> range:
    """Return ``key`` as a range of indices with respect to ``bound``"""
    return range(*key.indices(bound))


class Bits(Sequence[Bit]):
    """A compact, growable array of bits

    ``Bits`` objects maintain a basic size and an array of bytes. The actual
    bits are stored in the binary of these bytes to significantly reduce memory
    overhead.

    Note that deleting operations are currently unsupported, meaning that this
    type does not inherit from the built-in ``MutableSequence`` ABC.
    """

    __slots__ = ("_size", "_data")
    _size: int
    _data: bytearray

    def __init__(self, values: Iterable[object] = (), /) -> None:
        if isinstance(values, Bits):
            self._size = values._size
            self._data = values._data.copy()
        else:
            self._size = 0
            self._data = bytearray(operator.length_hint(values, 0) // BYTE_SIZE)
            self.extend(values)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}([{', '.join(map(repr, self))}])"

    def __len__(self) -> int:
        return self._size

    @overload
    def __getitem__(self, key: SupportsIndex, /) -> Bit: ...
    @overload
    def __getitem__(self, key: slice, /) -> Self: ...

    def __getitem__(self, key, /):
        if isinstance(key, slice):
            indices = self._resolve_slice(key)
            return self.__class__(map(self._get_bit, indices))
        else:
            index = self._resolve_index(key)
            return self._get_bit(index)

    @overload
    def __setitem__(self, key: SupportsIndex, value: object, /) -> None: ...
    @overload
    def __setitem__(self, key: slice, other: Sequence[object], /) -> None: ...

    def __setitem__(self, key, obj, /):
        if isinstance(key, slice):
            indices = self._resolve_slice(key)
            values  = obj
            if __debug__:
                m = len(indices)
                n = len(values)
                if m != n:
                    raise ValueError(f"{m} entries were selected, but sequence has {n} values")
            for index, value in zip(indices, values):
                self._set_bit(index, value)
        else:
            index = self._resolve_index(key)
            value = obj
            self._set_bit(index, value)

    def __iter__(self) -> Iterator[Bit]:
        indices = range(len(self))
        return map(self._get_bit, indices)

    def __reversed__(self) -> Iterator[Bit]:
        indices = range(len(self) - 1, -1, -1)
        return map(self._get_bit, indices)

    def __deepcopy__(self, memo: Optional[dict[int, object]] = None) -> Self:
        return self.__class__(self)

    __copy__ = __deepcopy__

    def _resolve_index(self, key: SupportsIndex) -> int:
        bound = len(self)
        try:
            index = resolve_index(key, bound)
        except IndexError:
            raise IndexError(f"array has {bound} bits, but index is {key}") from None
        else:
            return index

    def _resolve_slice(self, key: slice) -> range:
        bound = len(self)
        range = resolve_slice(key, bound)
        return range

    def _get_bit(self, index: int) -> Bit:
        byte_index, bit_index = divmod(index, BYTE_SIZE)
        byte = self._data[byte_index] >> bit_index
        mask = 1
        return byte & mask  # type: ignore

    def _set_bit(self, index: int, value: object) -> None:
        byte_index, bit_index = divmod(index, BYTE_SIZE)
        byte = self._data[byte_index]
        mask = 1 << bit_index
        if value:
            byte |= mask
        else:
            byte &= ~mask
        self._data[byte_index] = byte

    @classmethod
    def fill(cls, value: object, /, size: int) -> Self:
        """Return a new array of length ``size``, filled entirely by the truth
        of ``value``

        A negative ``size`` is treated as 0.
        """
        size = max(size, 0)
        byte_count, bit_count = divmod(size, BYTE_SIZE)
        data = bytearray(itertools.repeat(255 if value else 0, byte_count))
        if bit_count:
            data.append((2 ** bit_count - 1) if value else 0)
        self = cls.__new__(cls)
        self._size = size
        self._data = data
        return self

    @classmethod
    def zeros(cls, size: int) -> Self:
        """Return a new array of length ``size``, filled entirely by zeros"""
        return cls.fill(0, size)

    @classmethod
    def ones(cls, size: int) -> Self:
        """Return a new array of length ``size``, filled entirely by ones"""
        return cls.fill(1, size)

    def copy(self) -> Self:
        """Return a copy of the array"""
        return self.__copy__()

    def append(self, value: object, /) -> None:
        """Add the truth of ``value`` to the end of the array"""
        data = self._data
        size = self._size
        byte_index, bit_index = divmod(size, BYTE_SIZE)
        if len(data) == byte_index:
            data.append(0)
        if value:
            mask = 1 << bit_index
            data[byte_index] |= mask
        self._size = size + 1

    def extend(self, values: Iterable[object], /) -> None:
        """Append the truths of ``values`` to the end of the array"""
        for value in values:
            self.append(value)
