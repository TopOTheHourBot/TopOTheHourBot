from __future__ import annotations

import asyncio
from asyncio import TimeoutError as AsyncTimeoutError
from collections.abc import AsyncIterable, AsyncIterator, Callable
from typing import Optional, ParamSpec, TypeVar, cast, overload

__all__ = [
    "Routine",
    "routine",
]

P = ParamSpec("P")

T1 = TypeVar("T1")
T2 = TypeVar("T2")
T3 = TypeVar("T3")
T4 = TypeVar("T4")
T5 = TypeVar("T5")

S1 = TypeVar("S1")
S2 = TypeVar("S2")

T = TypeVar("T")
S = TypeVar("S")

T_co = TypeVar("T_co", covariant=True)
S_co = TypeVar("S_co", covariant=True)


def identity(value: T, /) -> T:
    """Return ``value``"""
    return value


def routine(func: Callable[P, AsyncIterable[T]], /) -> Callable[P, Routine[T]]:
    """Convert a function's return type from an ``AsyncIterable[T]`` to
    ``Routine[T]``
    """

    def routine_wrapper(*args: P.args, **kwargs: P.kwargs) -> Routine[T]:
        return Routine(func(*args, **kwargs))

    routine_wrapper.__name__ = func.__name__
    routine_wrapper.__doc__  = func.__doc__

    return routine_wrapper


class Routine(AsyncIterator[T_co]):
    """A wrapper type for asynchronous iterators that adds common iterable
    operations and waiting utilities
    """

    __slots__ = ("_values")
    _values: AsyncIterator[T_co]

    def __init__(self, values: AsyncIterable[T_co], /) -> None:
        self._values = aiter(values)

    async def __anext__(self) -> T_co:
        value = await anext(self._values)
        return value

    @routine
    async def stagger(self, delay: float, *, instant_first: bool = True) -> AsyncIterator[T_co]:
        """Return a sub-routine whose yields are staggered by at least
        ``delay`` seconds

        If ``instant_first`` is true, the first value is yielded without extra
        delay applied to the underlying iterator.
        """
        if instant_first:
            try:
                value = await anext(self)
            except StopAsyncIteration:
                return
            else:
                yield value
        async for value in self:
            await asyncio.sleep(delay)
            yield value

    @routine
    async def timeout(self, delay: float, *, infinite_first: bool = True) -> AsyncIterator[T_co]:
        """Return a sub-routine whose value retrievals are time restricted by
        ``delay`` seconds

        If ``infinite_first`` is true, the first retrieval is awaited for
        infinite time.
        """
        try:
            if infinite_first:
                yield await anext(self)
            while True:
                yield await asyncio.wait_for(anext(self), delay)
        except (StopAsyncIteration, AsyncTimeoutError):
            return

    @routine
    async def global_unique(self, key: Callable[[T_co], object] = identity) -> AsyncIterator[T_co]:
        """Return a sub-routine of the values whose call to ``key`` is unique
        among all encountered values

        Note that this method may require significant auxiliary storage,
        depending on how often unique values appear.
        """
        seen = set()
        async for value in self:
            result = key(value)
            if result not in seen:
                yield value
                seen.add(result)

    @routine
    async def local_unique(self, key: Callable[[T_co], object] = identity) -> AsyncIterator[T_co]:
        """Return a sub-routine of the values whose call to ``key`` is unique
        as compared to the previously encountered value
        """
        seen = object()
        async for value in self:
            result = key(value)
            if result != seen:
                yield value
                seen = result

    @routine
    async def enumerate(self, start: int = 0) -> AsyncIterator[tuple[int, T_co]]:
        """Return a sub-routine whose values are enumerated from ``start``"""
        index = start
        async for value in self:
            yield (index, value)
            index += 1

    @routine
    async def limit(self, bound: int) -> AsyncIterator[T_co]:
        """Return a sub-routine limited to the first ``bound`` values

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

    @routine
    async def map(self, mapper: Callable[[T_co], S]) -> AsyncIterator[S]:
        """Return a sub-routine of the results from passing each value to
        ``mapper``
        """
        async for value in self:
            yield mapper(value)

    @overload
    def zip(self: Routine[T1]) -> Routine[tuple[T1]]: ...
    @overload
    def zip(self: Routine[T1], other2: AsyncIterable[T2], /) -> Routine[tuple[T1, T2]]: ...
    @overload
    def zip(self: Routine[T1], other2: AsyncIterable[T2], other3: AsyncIterable[T3], /) -> Routine[tuple[T1, T2, T3]]: ...
    @overload
    def zip(self: Routine[T1], other2: AsyncIterable[T2], other3: AsyncIterable[T3], other4: AsyncIterable[T4], /) -> Routine[tuple[T1, T2, T3, T4]]: ...
    @overload
    def zip(self: Routine[T1], other2: AsyncIterable[T2], other3: AsyncIterable[T3], other4: AsyncIterable[T4], other5: AsyncIterable[T5], /) -> Routine[tuple[T1, T2, T3, T4, T5]]: ...
    @overload
    def zip(self, *others: AsyncIterable) -> Routine[tuple]: ...
    @routine
    async def zip(self, *others: AsyncIterable) -> AsyncIterator[tuple]:
        """Return a sub-routine zipped with other asynchronous iterables

        Iteration stops when the shortest iterable has been exhausted.
        """
        its = (self, *map(aiter, others))
        try:
            while True:
                yield await asyncio.gather(*map(anext, its))  # type: ignore
        except StopAsyncIteration:
            return

    @overload
    def star_map(self: Routine[tuple[T1]], mapper: Callable[[T1], S]) -> Routine[S]: ...
    @overload
    def star_map(self: Routine[tuple[T1, T2]], mapper: Callable[[T1, T2], S]) -> Routine[S]: ...
    @overload
    def star_map(self: Routine[tuple[T1, T2, T3]], mapper: Callable[[T1, T2, T3], S]) -> Routine[S]: ...
    @overload
    def star_map(self: Routine[tuple[T1, T2, T3, T4]], mapper: Callable[[T1, T2, T3, T4], S]) -> Routine[S]: ...
    @overload
    def star_map(self: Routine[tuple[T1, T2, T3, T4, T5]], mapper: Callable[[T1, T2, T3, T4, T5], S]) -> Routine[S]: ...
    @overload
    def star_map(self: Routine[tuple], mapper: Callable[..., S]) -> Routine[S]: ...
    @routine
    async def star_map(self: Routine[tuple], mapper: Callable[..., S]) -> AsyncIterator[S]:
        """Return a sub-routine of the results from unpacking and passing each
        ``tuple`` value to ``mapper``
        """
        async for values in self:
            yield mapper(*values)

    @routine
    async def filter(self, predicate: Callable[[T_co], object]) -> AsyncIterator[T_co]:
        """Return a sub-routine of the values whose call to ``predicate``
        evaluates true
        """
        async for value in self:
            if predicate(value):
                yield value

    def truthy(self) -> Routine[T_co]:
        """Return a sub-routine of the values filtered by their truthyness"""
        return self.filter(lambda value: value)

    def falsy(self) -> Routine[T_co]:
        """Return a sub-routine of the values filtered by their falsyness"""
        return self.filter(lambda value: not value)

    def not_none(self: Routine[Optional[S]]) -> Routine[S]:
        """Return a sub-routine of the values that are not ``None``"""
        return cast(Routine[S], self.filter(lambda value: value is not None))

    async def all(self) -> bool:
        """Return true if all values are true, otherwise false"""
        return bool(await anext(self.falsy(), True))

    async def any(self) -> bool:
        """Return true if any value is true, otherwise false"""
        return bool(await anext(self.truthy(), False))

    async def collect(self) -> list[T_co]:
        """Return the values accumulated as a ``list``"""
        results = []
        async for value in self:
            results.append(value)
        return results

    async def reduce(self, initial: S1, reducer: Callable[[S1, T_co], S1], finalizer: Callable[[S1], S2] = identity) -> S2:
        """Return the values accumulated as one via left-fold"""
        medial = initial
        async for value in self:
            medial = reducer(medial, value)
        result = finalizer(medial)
        return result

    async def count(self) -> int:
        """Return the number of values"""
        return await self.reduce(0, lambda count, _: count + 1)
