from __future__ import annotations

__all__ = ["Parser"]

from typing import Self, final


@final
class Parser:
    """A simple string parser

    Parser objects are a thin wrapper around a subject string, and an index
    that can be "moved" across it - commonly by targeting of sub-strings.
    """

    __slots__ = ("_subject", "_index")
    _subject: str
    _index: int

    def __init__(self, subject: str, *, index: int = 0) -> None:
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

    def peek[T](self, default: T = None) -> str | T:
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
        subject = self._subject
        i = self._index + exclude_current
        j = subject.find(target, i)
        if j == -1:
            j = len(subject)
        result = subject[i:j]
        self._index = j
        return result

    def take_all(self, *, exclude_current: bool = True) -> str:
        """Return a subset of the subject string up to its end, beginning from
        the current index

        Excludes the current value if ``exclude_current`` is true (the default).
        """
        subject = self._subject
        i = self._index + exclude_current
        result = subject[i:]
        self._index = len(subject)
        return result
