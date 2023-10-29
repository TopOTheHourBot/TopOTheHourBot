from __future__ import annotations

__all__ = [
    "Series",
    "series",
]

import asyncio
from asyncio import Task
from asyncio import TimeoutError as AsyncTimeoutError
from collections.abc import AsyncIterator, Callable
from typing import Optional, TypeGuard, final, overload


def identity[T](value: T, /) -> T:
    """Return ``value``"""
    return value


def not_none[T](value: Optional[T], /) -> TypeGuard[T]:
    """Return true if ``value`` is not ``None``, otherwise false"""
    return value is not None


def series[**P, T](func: Callable[P, AsyncIterator[T]], /) -> Callable[P, Series[T]]:
    """Convert a function's return type from an ``AsyncIterator[T]`` to
    ``Series[T]``
    """

    def series_wrapper(*args: P.args, **kwargs: P.kwargs) -> Series[T]:
        return Series(func(*args, **kwargs))

    series_wrapper.__name__ = func.__name__
    series_wrapper.__doc__  = func.__doc__

    return series_wrapper


@final
class Series[T](AsyncIterator[T]):
    """A wrapper type for asynchronous iterators that adds common iterable
    operations and waiting utilities
    """

    __slots__ = ("_values")
    _values: AsyncIterator[T]

    def __init__(self, values: AsyncIterator[T], /) -> None:
        self._values = values

    async def __anext__(self) -> T:
        value = await anext(self._values)
        return value

    @series
    async def stagger(self, delay: float, *, first: bool = False) -> AsyncIterator[T]:
        """Return a sub-series whose yields are staggered by at least ``delay``
        seconds

        Staggers before the first retrieval if ``first`` is true.
        """
        delay = max(0, delay)
        loop  = asyncio.get_running_loop()

        if first:
            await asyncio.sleep(delay)

        try:
            value = await anext(self)
        except StopAsyncIteration:
            return
        else:
            yield_time = loop.time()
            yield value

        async for value in self:
            current_time = loop.time()
            sleep_time = max(0, delay - (current_time - yield_time))
            yield_time = current_time + sleep_time
            if sleep_time:
                await asyncio.sleep(sleep_time)
            yield value

    @series
    async def timeout(self, delay: float, *, first: bool = False) -> AsyncIterator[T]:
        """Return a sub-series whose value retrievals are time restricted by
        ``delay`` seconds

        Timeout is applied to the first retrieval if ``first`` is true.
        """
        try:
            if not first:
                yield await anext(self)
            while True:
                yield await asyncio.wait_for(anext(self), delay)
        except (StopAsyncIteration, AsyncTimeoutError):
            return

    @series
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

    @series
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

    @series
    async def enumerate(self, start: int = 0) -> AsyncIterator[tuple[int, T]]:
        """Return a sub-series whose values are enumerated from ``start``"""
        index = start
        async for value in self:
            yield (index, value)
            index += 1

    @series
    async def limit(self, bound: int) -> AsyncIterator[T]:
        """Return a sub-series limited to the first ``bound`` values

        Negative values for ``bound`` are treated equivalently to 0.
        """
        if bound <= 0:
            return
        count = 1
        async for value in self:
            yield value
            if count == bound:
                return
            count += 1

    @series
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
    @series
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

    @series
    async def broadcast[*Ts](self, *others: *Ts) -> AsyncIterator[tuple[T, *Ts]]:
        """Return a sub-series of the values zipped with repeated objects"""
        async for value in self:
            yield (value, *others)

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
    @series
    async def merge(self, *others: Series) -> AsyncIterator:
        """Return a sub-series merged with other series

        Iteration stops when the longest series has been exhausted.
        """
        its = {
            str(name): it
            for name, it in enumerate((self, *others))
        }

        todo = set[Task]()
        for name, it in its.items():
            task = asyncio.create_task(anext(it), name=name)
            todo.add(task)

        while todo:
            done, todo = await asyncio.wait(todo, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                name = task.get_name()
                try:
                    result = task.result()
                except StopAsyncIteration:
                    del its[name]
                    continue
                else:
                    it = its[name]
                    task = asyncio.create_task(anext(it), name=name)
                    todo.add(task)
                    yield result

    @series
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
    @series
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
        async for value in self:
            result.append(value)
        return result

    async def reduce[S](self, initial: S, reducer: Callable[[S, T], S]) -> S:
        """Return the values accumulated as one via left-fold"""
        result = initial
        async for value in self:
            result = reducer(result, value)
        return result

    async def count(self) -> int:
        """Return the number of values"""
        return await self.reduce(0, lambda count, _: count + 1)
