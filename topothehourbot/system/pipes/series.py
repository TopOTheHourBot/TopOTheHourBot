from __future__ import annotations

__all__ = ["Series"]

import asyncio
from asyncio import Task
from asyncio import TimeoutError as AsyncTimeoutError
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Optional, Self, TypeGuard, final, overload


def identity[T](value: T, /) -> T:
    """Return ``value``"""
    return value


def not_none[T](value: Optional[T], /) -> TypeGuard[T]:
    """Return true if ``value`` is not ``None``, otherwise false"""
    return value is not None


@final
@dataclass(slots=True)
class Reduction[T]:
    """A box type returned by ``Series.reduce()``

    Contains the reduction value and a flag indicating whether it is the same
    as the initial value, under the attributes ``value`` and ``initial``,
    respectively.

    The truth value of a ``Reduction`` object is true if ``not initial``.
    """

    value: T
    initial: bool = False

    def __bool__(self) -> bool:
        return not self.initial


@final
class Series[T](AsyncIterator[T]):
    """A wrapper type for asynchronous iterators that adds common iterable
    operations and waiting utilities
    """

    __slots__ = ("_values")
    _values: AsyncIterator[T]

    def __init__(self, values: AsyncIterator[T], /) -> None:
        self._values = values

    def __aiter__(self) -> Self:
        return self

    async def __anext__(self) -> T:
        value = await anext(self._values)
        return value

    @staticmethod
    def from_generator[**P, S](func: Callable[P, AsyncIterator[S]], /) -> Callable[P, Series[S]]:
        """Convert a function's return type from an asynchronous iterator to a
        ``Series``
        """

        def wrapper(*args: P.args, **kwargs: P.kwargs) -> Series[S]:
            return Series(func(*args, **kwargs))

        wrapper.__name__ = func.__name__
        wrapper.__doc__  = func.__doc__

        return wrapper

    @from_generator
    async def finite_timeout(self, delay: float, *, first: bool = False) -> AsyncIterator[T]:
        """Return a sub-series whose value retrievals are time restricted by
        ``delay`` seconds

        If ``first`` is true, applies the timeout while awaiting the first
        value. False by default.
        """
        try:
            if not first:
                yield await anext(self)
            while True:
                yield await asyncio.wait_for(anext(self), delay)
        except (StopAsyncIteration, AsyncTimeoutError):
            return

    def timeout(self, delay: Optional[float], *, first: bool = False) -> Series[T]:
        """Return a sub-series whose value retrievals are optionally time
        restricted by ``delay`` seconds

        If ``delay`` is ``None``, do not apply a timeout.

        If ``first`` is true, applies the timeout while awaiting the first
        value. False by default.
        """
        if delay is None:  # Reduces layers of composition
            return self
        return self.finite_timeout(delay, first=first)

    @from_generator
    async def global_unique(self, key: Callable[[T], object] = identity) -> AsyncIterator[T]:
        """Return a sub-series of the values whose call to ``key`` is unique
        among all encountered values
        """
        seen = set[object]()
        async for value in self:
            result = key(value)
            if result not in seen:
                seen.add(result)
                yield value

    @from_generator
    async def local_unique(self, key: Callable[[T], object] = identity) -> AsyncIterator[T]:
        """Return a sub-series of the values whose call to ``key`` is unique
        as compared to the previously encountered value
        """
        seen = object()
        async for value in self:
            result = key(value)
            if result != seen:
                seen = result
                yield value

    @from_generator
    async def enumerate(self, start: int = 0) -> AsyncIterator[tuple[int, T]]:
        """Return a sub-series whose values are enumerated from ``start``"""
        index = start
        async for value in self:
            yield (index, value)
            index += 1

    @from_generator
    async def limit(self, bound: int) -> AsyncIterator[T]:
        """Return a sub-series limited to the first ``bound`` values

        Negative values for ``bound`` are treated equivalently to 0.
        """
        if bound <= 0:
            return
        async for count, value in self.enumerate(1):
            yield value
            if count == bound:
                return

    @from_generator
    async def map[S](self, mapper: Callable[[T], S]) -> AsyncIterator[S]:
        """Return a sub-series of the results from passing each value to
        ``mapper``
        """
        async for value in self:
            yield mapper(value)

    @overload
    def zip(self) -> Series[tuple[T]]: ...
    @overload
    def zip[T1](self, other1: Series[T1], /) -> Series[tuple[T, T1]]: ...
    @overload
    def zip[T1, T2](self, other1: Series[T1], other2: Series[T2], /) -> Series[tuple[T, T1, T2]]: ...
    @overload
    def zip[T1, T2, T3](self, other1: Series[T1], other2: Series[T2], other3: Series[T3], /) -> Series[tuple[T, T1, T2, T3]]: ...
    @overload
    def zip[T1, T2, T3, T4](self, other1: Series[T1], other2: Series[T2], other3: Series[T3], other4: Series[T4], /) -> Series[tuple[T, T1, T2, T3, T4]]: ...
    @overload
    def zip(self, *others: Series) -> Series[tuple]: ...
    @from_generator
    async def zip(self, *others: Series) -> AsyncIterator[tuple]:
        """Return a sub-series zipped with other series

        Iteration stops when the shortest series has been exhausted.
        """
        its = (self, *others)
        try:
            while True:
                yield tuple(await asyncio.gather(*map(anext, its)))
        except StopAsyncIteration:
            return

    @overload
    def merge(self) -> Series[T]: ...
    @overload
    def merge[T1](self, other1: Series[T1], /) -> Series[T | T1]: ...
    @overload
    def merge[T1, T2](self, other1: Series[T1], other2: Series[T2], /) -> Series[T | T1 | T2]: ...
    @overload
    def merge[T1, T2, T3](self, other1: Series[T1], other2: Series[T2], other3: Series[T3], /) -> Series[T | T1 | T2 | T3]: ...
    @overload
    def merge[T1, T2, T3, T4](self, other1: Series[T1], other2: Series[T2], other3: Series[T3], other4: Series[T4], /) -> Series[T | T1 | T2 | T3 | T4]: ...
    @overload
    def merge(self, *others: Series) -> Series: ...
    @from_generator
    async def merge(self, *others: Series) -> AsyncIterator:
        """Return a sub-series merged with other series

        Iteration stops when the longest series has been exhausted.
        """
        map = dict[str, Series]()
        map["0"] = self
        for n, series in enumerate(others, 1):
            map[f"{n}"] = series

        todo = set[Task]()
        for name, series in map.items():
            task = asyncio.create_task(anext(series), name=name)
            todo.add(task)

        while todo:
            done, todo = await asyncio.wait(todo, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                name = task.get_name()
                try:
                    result = task.result()
                except StopAsyncIteration:
                    # Series has been exhausted: no need to keep a reference at
                    # this point
                    del map[name]
                    continue
                else:
                    # Series has yielded: await its next value and return the
                    # current one
                    series = map[name]
                    task = asyncio.create_task(anext(series), name=name)
                    todo.add(task)
                    yield result

    @from_generator
    async def star_map[*Ts, S](self: Series[tuple[*Ts]], mapper: Callable[[*Ts], S]) -> AsyncIterator[S]:
        """Return a sub-series of the results from unpacking and passing each
        value to ``mapper``
        """
        async for values in self:
            yield mapper(*values)

    @overload
    def filter[S](self, predicate: Callable[[T], TypeGuard[S]]) -> Series[S]: ...
    @overload
    def filter(self, predicate: Callable[[T], object]) -> Series[T]: ...
    @from_generator
    async def filter(self, predicate: Callable[[T], object]) -> AsyncIterator[T]:
        """Return a sub-series of the values whose call to ``predicate``
        evaluates true
        """
        async for value in self:
            if predicate(value):
                yield value

    def truthy(self) -> Series[T]:
        """Return a sub-series of the values filtered by their truthyness"""
        return self.filter(lambda value: value)

    def falsy(self) -> Series[T]:
        """Return a sub-series of the values filtered by their falsyness"""
        return self.filter(lambda value: not value)

    def not_none[S](self: Series[Optional[S]]) -> Series[S]:
        """Return a sub-series of the values that are not ``None``"""
        return self.filter(not_none)

    async def all(self) -> bool:
        """Return true if all values are true, otherwise false"""
        return bool(await anext(self.falsy(), True))

    async def any(self) -> bool:
        """Return true if any value is true, otherwise false"""
        return bool(await anext(self.truthy(), False))

    async def collect(self) -> list[T]:
        """Return the values accumulated as a ``list``"""
        result = []
        async for value in self:  # This could be a call to reduce() if
            result.append(value)  # list.append() returned self 😔
        return result

    async def reduce[S](self, initial: S, reducer: Callable[[S, T], S]) -> Reduction[S]:
        """Return the values accumulated as one via left-fold"""
        result = initial
        try:
            value = await anext(self)
        except StopAsyncIteration:
            return Reduction(result, initial=True)
        else:
            result = reducer(result, value)
        async for value in self:
            result = reducer(result, value)
        return Reduction(result)

    async def count(self) -> int:
        """Return the number of values"""
        reduction = await self.reduce(0, lambda count, _: count + 1)
        return reduction.value
