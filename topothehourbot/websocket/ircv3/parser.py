from __future__ import annotations

from typing import Self, TypeVar

__all__ = ["Parser"]

DefaultT = TypeVar("DefaultT")


class Parser:

    __slots__ = ("_subject", "_index")

    _subject: str
    _index: int

    def __init__(self, subject: str, index: int = 0) -> None:
        self._subject = subject
        self._index = index

    def __repr__(self) -> str:
        return f"Parser(subject={self._subject!r}, index={self._index!r})"

    @property
    def subject(self) -> str:
        """The subject string"""
        return self._subject

    @property
    def index(self) -> int:
        """The current index"""
        return self._index

    def ok(self) -> bool:
        """Return true if the index is within range of the subject string,
        otherwise false
        """
        return 0 <= self._index < len(self._subject)

    def advance(self, steps: int = 1) -> Self:
        """Advance the index by ``steps`` and return the parser"""
        self._index += steps
        return self

    def peek(self, default: DefaultT = None) -> str | DefaultT:
        """Return the value at the current index, or ``default`` if the index
        is out of range

        This method does not advance the index.
        """
        try:
            result = self._subject[self._index]
        except IndexError:
            return default
        else:
            return result

    def take_until(self, target: str = " ", *, exclude_current: bool = True) -> str:
        """Return a subset of the subject string up to, but not including, the
        first instance of ``target`` beginning from the current index, or all
        remaining characters if ``target`` is not found

        Excludes the current value if ``exclude_current`` is true (the default).

        Advances the index to the position of ``target``'s first character if
        discovered, otherwise the length of the subject string.
        """
        i = self._index + exclude_current
        j = self._subject.find(target, i)
        if j < 0:
            j = None
        result = self._subject[i:j]
        self._index = j
        return result

    def take_all(self, *, exclude_current: bool = True) -> str:
        """Return a subset of the subject string up to its end, beginning from
        the current index

        Excludes the current value if ``exclude_current`` is true (the default).
        """
        i = self._index + exclude_current
        result = self._subject[i:]
        self._index = len(self._subject)
        return result
