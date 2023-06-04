from __future__ import annotations

import asyncio
from asyncio import TimeoutError as AsyncTimeoutError
from collections.abc import AsyncIterable, AsyncIterator, Callable
from typing import Literal, Optional, ParamSpec, TypeVar, cast, overload

__all__ = ["Routine", "routine"]

P = ParamSpec("P")

T1 = TypeVar("T1")
T2 = TypeVar("T2")
T3 = TypeVar("T3")
T4 = TypeVar("T4")
T5 = TypeVar("T5")

T = TypeVar("T")
T_co = TypeVar("T_co", covariant=True)

S = TypeVar("S")
S_co = TypeVar("S_co", covariant=True)


def routine(func: Callable[P, AsyncIterable[T]], /) -> Callable[P, Routine[T]]:
    """Cast a function's return type from an ``AsyncIterable[T]`` to
    ``Routine[T]``
    """

    def routine_wrapper(*args: P.args, **kwargs: P.kwargs) -> Routine[T]:
        return Routine(func(*args, **kwargs))

    routine_wrapper.__name__ = func.__name__
    routine_wrapper.__doc__  = func.__doc__

    return routine_wrapper


class Routine(AsyncIterator[T_co]):

    __slots__ = ("_values")

    _values: AsyncIterator[T_co]

    def __init__(self, values: AsyncIterable[T_co]) -> None:
        self._values = aiter(values)

    async def __anext__(self) -> T_co:
        return await anext(self._values)  # type: ignore

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
    async def unique_global(self, key: Callable[[T_co], S] = lambda value: value) -> AsyncIterator[T_co]:
        """Return a sub-routine whose call to ``key`` is unique among all
        encountered values
        """
        seen = set()
        async for value in self:
            result = key(value)
            if result not in seen:
                yield value
                seen.add(result)

    @routine
    async def unique_local(self, key: Callable[[T_co], S] = lambda value: value) -> AsyncIterator[T_co]:
        """Return a sub-routine whose call to ``key`` is unique as compared to
        the previously encountered value
        """
        seen = object()
        async for value in self:
            result = key(value)
            if result != seen:
                yield value
                seen = result

    @routine
    async def enumerate(self, start: int = 0) -> AsyncIterator[tuple[int, T_co]]:
        """Return a sub-routine of the values packed with an index that
        increments by 1, beginning at ``start``
        """
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
    def unpack_map(self: Routine[tuple[T1]], mapper: Callable[[T1], S]) -> Routine[S]: ...
    @overload
    def unpack_map(self: Routine[tuple[T1, T2]], mapper: Callable[[T1, T2], S]) -> Routine[S]: ...
    @overload
    def unpack_map(self: Routine[tuple[T1, T2, T3]], mapper: Callable[[T1, T2, T3], S]) -> Routine[S]: ...
    @overload
    def unpack_map(self: Routine[tuple[T1, T2, T3, T4]], mapper: Callable[[T1, T2, T3, T4], S]) -> Routine[S]: ...
    @overload
    def unpack_map(self: Routine[tuple[T1, T2, T3, T4, T5]], mapper: Callable[[T1, T2, T3, T4, T5], S]) -> Routine[S]: ...
    @overload
    def unpack_map(self: Routine[tuple], mapper: Callable[..., S]) -> Routine[S]: ...
    @routine
    async def unpack_map(self: Routine[tuple], mapper: Callable[..., S]) -> AsyncIterator[S]:
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
        """Return a sub-routine of values filtered by their truthyness"""
        return self.filter(lambda value: value)

    def falsey(self) -> Routine[T_co]:
        """Return a sub-routine of values filtered by their falseyness"""
        return self.filter(lambda value: not value)

    def not_none(self: Routine[Optional[T]]) -> Routine[T]:
        """Return a sub-routine of values that are not ``None``"""
        return cast(Routine[T], self.filter(lambda value: value is not None))

    async def all(self) -> bool:
        """Return true if all values are true, otherwise false"""
        return bool(await anext(self.falsey(), True))

    async def any(self) -> bool:
        """Return true if any value is true, otherwise false"""
        return bool(await anext(self.truthy(), False))

    async def collect(self) -> list[T_co]:
        """Return the values as a ``list``"""
        results = []
        async for value in self:
            results.append(value)
        return results

    async def reduce(self, initial: S, reducer: Callable[[S, T_co], S]) -> S:
        """Return the result of accumulating values onto ``initial`` via
        repeated calls to ``reducer``
        """
        result = initial
        async for value in self:
            result = reducer(result, value)
        return result

    async def count(self) -> int:
        """Return the number of values"""
        return await self.reduce(0, lambda count, value: count + 1)
