from __future__ import annotations

__all__ = [
    "Stream",
    "Merger",
    "compose",
    "merge",
]

import asyncio
import logging
from asyncio import Task
from asyncio import TimeoutError as AsyncTimeoutError
from collections import deque as Deque
from collections.abc import AsyncIterator, Callable
from typing import Any, Self, TypeGuard, final, overload


def identity[T](value: T, /) -> T:
    """Return ``value``"""
    return value


def not_none[T](value: T | None, /) -> TypeGuard[T]:
    """Return true if ``value`` is not ``None``, otherwise false"""
    return value is not None


def compose[**P, T](func: Callable[P, AsyncIterator[T]]) -> Callable[P, Stream[T]]:
    """Convert a function's return type from an asynchronous iterator to a
    ``Stream``
    """

    def compose_wrapper(*args: P.args, **kwargs: P.kwargs) -> Stream[T]:
        return Stream(func(*args, **kwargs))

    compose_wrapper.__name__ = func.__name__
    compose_wrapper.__doc__ = func.__doc__

    return compose_wrapper


@final
class Stream[T](AsyncIterator[T]):
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

    @compose
    async def finite_timeout(self, delay: float, *, first: bool = True) -> AsyncIterator[T]:
        """Return a sub-stream whose value retrievals are time restricted by
        ``delay`` seconds

        If ``first`` is false, do not apply timeout to the first retrieval.
        """
        try:
            if not first:
                yield await anext(self)
            while True:
                yield await asyncio.wait_for(anext(self), delay)
        except (StopAsyncIteration, AsyncTimeoutError):
            return

    def timeout(self, delay: float | None, *, first: bool = True) -> Stream[T]:
        """Return a sub-stream whose value retrievals are optionally time
        restricted by ``delay`` seconds

        If ``delay`` is ``None``, do not apply a timeout.

        If ``first`` is false, do not apply timeout to the first retrieval.
        """
        if delay is None:  # Reduces layers of composition
            return self
        return self.finite_timeout(delay, first=first)

    @compose
    async def global_unique(self, key: Callable[[T], object] = identity) -> AsyncIterator[T]:
        """Return a sub-stream of the values whose call to ``key`` is unique
        among all encountered values
        """
        seen = set[object]()
        async for value in self:
            result = key(value)
            if result not in seen:
                seen.add(result)
                yield value

    @compose
    async def local_unique(self, key: Callable[[T], object] = identity) -> AsyncIterator[T]:
        """Return a sub-stream of the values whose call to ``key`` is unique
        as compared to the previously encountered value
        """
        seen = object()
        async for value in self:
            result = key(value)
            if result != seen:
                seen = result
                yield value

    @compose
    async def enumerate(self, start: int = 0) -> AsyncIterator[tuple[int, T]]:
        """Return a sub-stream whose values are enumerated from ``start``"""
        index = start
        async for value in self:
            yield (index, value)
            index += 1

    @compose
    async def finite_limit(self, bound: int) -> AsyncIterator[T]:
        """Return a sub-stream limited to the first ``bound`` values

        Negative values for ``bound`` are treated equivalently to 0.
        """
        if bound <= 0:
            return
        async for count, value in self.enumerate(1):
            yield value
            if count == bound:
                return

    def limit(self, bound: int | None) -> Stream[T]:
        """Return a sub-stream limited to the first ``bound`` values

        If ``bound`` is ``None``, do not apply a limit.

        Negative values for ``bound`` are treated equivalently to 0.
        """
        if bound is None:
            return self
        return self.finite_limit(bound)

    @compose
    async def map[S](self, mapper: Callable[[T], S]) -> AsyncIterator[S]:
        """Return a sub-stream of the results from passing each value to
        ``mapper``
        """
        async for value in self:
            yield mapper(value)

    @compose
    async def star_map[*Ts, S](self: Stream[tuple[*Ts]], mapper: Callable[[*Ts], S]) -> AsyncIterator[S]:
        """Return a sub-stream of the results from unpacking and passing each
        value to ``mapper``
        """
        async for values in self:
            yield mapper(*values)

    @overload
    def zip(self) -> Stream[tuple[T]]: ...
    @overload
    def zip[T1](self, other1: Stream[T1], /) -> Stream[tuple[T, T1]]: ...
    @overload
    def zip[T1, T2](self, other1: Stream[T1], other2: Stream[T2], /) -> Stream[tuple[T, T1, T2]]: ...
    @overload
    def zip[T1, T2, T3](self, other1: Stream[T1], other2: Stream[T2], other3: Stream[T3], /) -> Stream[tuple[T, T1, T2, T3]]: ...
    @overload
    def zip[T1, T2, T3, T4](self, other1: Stream[T1], other2: Stream[T2], other3: Stream[T3], other4: Stream[T4], /) -> Stream[tuple[T, T1, T2, T3, T4]]: ...
    @overload
    def zip(self, *others: Stream[Any]) -> Stream[tuple[Any, ...]]: ...
    @compose
    async def zip(self, *others: Stream[Any]) -> AsyncIterator[tuple[Any, ...]]:
        """Return a sub-stream zipped with other streams

        Iteration stops when the shortest stream has been exhausted.
        """
        streams = (self, *others)
        try:
            while True:
                yield tuple(await asyncio.gather(*map(anext, streams)))
        except StopAsyncIteration:
            return

    @overload
    def filter[S](self, predicate: Callable[[T], TypeGuard[S]]) -> Stream[S]: ...
    @overload
    def filter(self, predicate: Callable[[T], object]) -> Stream[T]: ...
    @compose
    async def filter(self, predicate: Callable[[T], object]) -> AsyncIterator[T]:
        """Return a sub-stream of the values whose call to ``predicate``
        evaluates true
        """
        async for value in self:
            if predicate(value):
                yield value

    @compose
    async def star_filter[*Ts](self: Stream[tuple[*Ts]], predicate: Callable[[*Ts], object]) -> AsyncIterator[tuple[*Ts]]:
        async for values in self:
            if predicate(*values):
                yield values

    @overload
    def chain(self) -> Stream[T]: ...
    @overload
    def chain[T1](self, other1: Stream[T1], /) -> Stream[T | T1]: ...
    @overload
    def chain[T1, T2](self, other1: Stream[T1], other2: Stream[T2], /) -> Stream[T | T1 | T2]: ...
    @overload
    def chain[T1, T2, T3](self, other1: Stream[T1], other2: Stream[T2], other3: Stream[T3], /) -> Stream[T | T1 | T2 | T3]: ...
    @overload
    def chain[T1, T2, T3, T4](self, other1: Stream[T1], other2: Stream[T2], other3: Stream[T3], other4: Stream[T4], /) -> Stream[T | T1 | T2 | T3 | T4]: ...
    @overload
    def chain(self, *others: Stream[Any]) -> Stream[Any]: ...
    @compose
    async def chain(self, *others: Stream[Any]) -> AsyncIterator[Any]:
        """Return a sub-stream chained with other streams"""
        async for value in self:
            yield value
        for other in others:
            async for value in other:
                yield value

    @compose
    async def break_if(self, predicate: Callable[[T], object]) -> AsyncIterator[T]:
        """Return a sub-stream that breaks when ``predicate`` evaluates true"""
        async for value in self:
            if predicate(value):
                break
            yield value

    def truthy(self) -> Stream[T]:
        """Return a sub-stream of the values filtered by their truthyness"""
        return self.filter(lambda value: value)

    def falsy(self) -> Stream[T]:
        """Return a sub-stream of the values filtered by their falsyness"""
        return self.filter(lambda value: not value)

    def not_none[S](self: Stream[S | None]) -> Stream[S]:
        """Return a sub-stream of the values that are not ``None``"""
        return self.filter(not_none)

    async def all(self) -> bool:
        """Return true if all values are true, otherwise false"""
        return bool(await self.falsy().next(default=True))

    async def any(self) -> bool:
        """Return true if any value is true, otherwise false"""
        return bool(await self.truthy().next(default=False))

    async def collect(self) -> list[T]:
        """Return the values accumulated as a ``list``"""
        result = list[T]()
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

    async def next[DefaultT](self, *, default: DefaultT = None) -> T | DefaultT:
        """Return the next value of the stream, or ``default`` if the stream is
        empty
        """
        return await anext(self, default)

    async def exhaust(self) -> None:
        """Consume the stream's remaining values"""
        async for _ in self:
            ...


@final
class Merger[T]:
    """An asynchronous iterable that "merges" the results of multiple
    ``Stream``s into one that ends when the longest of which has been exhausted

    ``Stream`` instances can be added before, or during iteration through the
    ``add()`` method. See its documentation for more details.

    If ``suppress_exceptions`` is true, streams that except while iterating
    will have their exceptions logged rather than propagated.
    """

    __slots__ = ("_suppress_exceptions", "_streams")
    _suppress_exceptions: bool
    _streams: Deque[Stream[T]]

    def __init__(self, *, suppress_exceptions: bool = False) -> None:
        self._suppress_exceptions = suppress_exceptions
        self._streams = Deque()

    @compose
    async def __aiter__(self) -> AsyncIterator[T]:
        done = dict[Task[T], Stream[T]]()
        todo = dict[Task[T], Stream[T]]()
        wake = asyncio.get_running_loop().create_future()

        def todo_to_done(task: Task[T]) -> None:
            done[task] = todo.pop(task)
            if not wake.done():
                wake.set_result(None)

        suppress_exceptions = self._suppress_exceptions

        streams = self._streams  # Reference to allow mid-iteration adds
        results = Deque[T]()

        def to_todo() -> None:
            while streams:
                stream = streams.popleft()
                task = asyncio.create_task(anext(stream))
                todo[task] = stream
                task.add_done_callback(todo_to_done)

        # This order of operations, while seemingly odd, is actually very
        # purposeful.

        # The anext() calls to each stream are dispatched as tasks *before*
        # yielding so that they may be finished while the iterating code
        # performs other, potentially asynchronous operations, hence why
        # results are gathered and taken from a queue rather than yielded as
        # soon as they are known.

        while True:

            while streams:
                stream = streams.popleft()
                task = asyncio.create_task(anext(stream))
                todo[task] = stream
                task.add_done_callback(todo_to_done)

            while results:
                result = results.popleft()
                yield result

            # The done map may contain tasks while the todo map doesn't. This
            # can occur if the iterating code awaits post-yield, allowing some
            # or all anext() tasks to complete.

            if not (todo or done):
                return

            await wake
            wake = asyncio.get_running_loop().create_future()

            while done:
                task, stream = done.popitem()
                try:
                    result = task.result()
                except StopAsyncIteration:
                    continue
                except Exception:
                    if suppress_exceptions:
                        logging.exception("Stream excepted during Merger iteration")
                        continue
                    else:
                        for task in todo:
                            task.cancel()
                        raise
                except BaseException:
                    for task in todo:
                        task.cancel()
                    raise
                else:
                    streams.append(stream)
                    results.append(result)

    def add(self, stream: Stream[T]) -> None:
        """Add a stream to the merger

        Additions can be made prior to, or during iteration. The first of the
        stream's yields will not always be awaited on subsequent continues of a
        ``Merger`` iteration, as streams that yield at the exact same moment in
        time are synchronously yielded.
        """
        self._streams.append(stream)


@overload
def merge(*, suppress_exceptions: bool = False) -> Merger[Any]: ...
@overload
def merge[T1](stream1: Stream[T1], /, *, suppress_exceptions: bool = False) -> Merger[T1]: ...
@overload
def merge[T1, T2](stream1: Stream[T1], stream2: Stream[T2], /, *, suppress_exceptions: bool = False) -> Merger[T1 | T2]: ...
@overload
def merge[T1, T2, T3](stream1: Stream[T1], stream2: Stream[T2], stream3: Stream[T3], /, *, suppress_exceptions: bool = False) -> Merger[T1 | T2 | T3]: ...
@overload
def merge[T1, T2, T3, T4](stream1: Stream[T1], stream2: Stream[T2], stream3: Stream[T3], stream4: Stream[T4], /, *, suppress_exceptions: bool = False) -> Merger[T1 | T2 | T3 | T4]: ...
@overload
def merge[T1, T2, T3, T4, T5](stream1: Stream[T1], stream2: Stream[T2], stream3: Stream[T3], stream4: Stream[T4], stream5: Stream[T5], /, *, suppress_exceptions: bool = False) -> Merger[T1 | T2 | T3 | T4 | T5]: ...
@overload
def merge(*streams: Stream[Any], suppress_exceptions: bool = False) -> Merger[Any]: ...

def merge(*streams: Stream[Any], suppress_exceptions: bool = False) -> Merger[Any]:
    """Return an asynchronous iterable that awaits its values from the given
    streams as a singular stream

    The object returned by this function supports addition of streams after its
    creation, even while iterating. See the ``Merger`` documentation for more
    details.
    """
    merger = Merger[Any](suppress_exceptions=suppress_exceptions)
    for stream in streams:
        merger.add(stream)
    return merger
