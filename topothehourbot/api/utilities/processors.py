from __future__ import annotations

__all__ = [
    "Processor",
    "Signal",
    "Success",
    "Failure",
    "Job",
    "BufferedJob",
    "job",
]

import asyncio
import functools
import logging
from abc import ABCMeta, abstractmethod
from asyncio import CancelledError, Task
from collections.abc import Callable, Coroutine, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Concatenate, Literal, Self, final, override

from .buffers import Buffer


class Processor[**ParamTs, ResultT](metaclass=ABCMeta):

    __slots__ = ("_tasks",)
    _tasks: set[Task[None]]

    def __init__(self) -> None:
        super().__init__()
        self._tasks = set()

    def _on_task_done(self, task: Task[None]) -> None:
        self._tasks.discard(task)

    @abstractmethod
    async def process(self, *args: ParamTs.args, **kwargs: ParamTs.kwargs) -> ResultT:
        """The procedure to execute"""
        raise NotImplementedError

    async def process_executor(self, *args: ParamTs.args, **kwargs: ParamTs.kwargs) -> None:
        await self.process(*args, **kwargs)

    def run(self, *args: ParamTs.args, **kwargs: ParamTs.kwargs) -> Task[None]:
        """Run ``process()`` as a task"""
        task = asyncio.create_task(self.process_executor(*args, **kwargs))
        self._tasks.add(task)
        task.add_done_callback(self._on_task_done)
        return task

    def cancel(self) -> None:
        """Cancel all ``process()`` executions

        To cancel a particular execution, invoke the ``cancel()`` method of the
        object returned by ``run()``.
        """
        tasks = self._tasks
        for task in tasks:
            task.cancel()
        tasks.clear()  # Ensure self.running() -> 0

    def running(self) -> int:
        """Return the current number of executions"""
        return len(self._tasks)


class Signal[**ParamTs, ResultT](Processor[ParamTs, None]):

    __slots__ = ("_callbacks",)
    _callbacks: set[Callable[ParamTs, Coroutine[Any, Any, ResultT]]]

    def __init__(self) -> None:
        super().__init__()
        self._callbacks = set()

    @override
    async def process(self, *args: ParamTs.args, **kwargs: ParamTs.kwargs) -> None:
        """Dispatch all callbacks as a task and await their returns"""
        loop = asyncio.get_running_loop()

        tasks = set[Task[ResultT]]()
        for callback in self._callbacks:
            task = loop.create_task(callback(*args, **kwargs))
            tasks.add(task)  # type: ignore

        for waiter in asyncio.as_completed(tasks):
            try:
                await waiter
            except CancelledError:
                for task in tasks:
                    task.cancel()
                return
            except Exception:
                # TODO: Write to own logger instance
                logging.exception("Callback excepted during Signal processing")

    def callback(self, callback: Callable[ParamTs, Coroutine[Any, Any, ResultT]]) -> Callable[ParamTs, Coroutine[Any, Any, ResultT]]:
        """Decorate a callback to schedule upon the signal's emission"""
        self.add_callback(callback)
        return callback

    def callback_partial(self, *args: Any, **kwargs: Any) -> Callable[[Callable[..., Coroutine[Any, Any, ResultT]]], Callable[ParamTs, Coroutine[Any, Any, ResultT]]]:
        """Decorate a callback to schedule upon the signal's emission,
        partially applying the given arguments, alike ``functools.partial()``
        """

        def callback_partial_decorator(func: Callable[..., Coroutine[Any, Any, ResultT]]) -> Callable[ParamTs, Coroutine[Any, Any, ResultT]]:

            async def callback_partial_wrapper(*other_args: ParamTs.args, **other_kwargs: ParamTs.kwargs) -> ResultT:
                return await func(*args, *other_args, **(kwargs | other_kwargs))

            self.add_callback(callback_partial_wrapper)

            return callback_partial_wrapper

        return callback_partial_decorator

    @contextmanager
    def callback_manager(self, callback: Callable[ParamTs, Coroutine[Any, Any, ResultT]]) -> Iterator[Self]:
        self.add_callback(callback)
        try:
            yield self
        finally:
            self.remove_callback(callback)

    def add_callback(self, callback: Callable[ParamTs, Coroutine[Any, Any, ResultT]]) -> Self:
        """Add a callback to schedule upon the signal's emission"""
        self._callbacks.add(callback)
        return self

    def remove_callback(self, callback: Callable[ParamTs, Coroutine[Any, Any, ResultT]]) -> Self:
        """Remove a callback to schedule upon the signal's emission"""
        self._callbacks.discard(callback)
        return self

    def maybe_run(self, *args: ParamTs.args, **kwargs: ParamTs.kwargs) -> Task[None] | None:
        """Schedule ``process()`` as a task if containing at least one
        callback, otherwise do nothing
        """
        if self._callbacks:
            return self.run(*args, **kwargs)


@dataclass(slots=True, eq=False, frozen=True)
class Result[T](metaclass=ABCMeta):

    value: T

    @abstractmethod
    def success(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def failure(self) -> bool:
        raise NotImplementedError


@final
@dataclass(slots=True, eq=False, frozen=True)
class Success[T](Result[T]):

    @override
    def success(self) -> Literal[True]:
        return True

    @override
    def failure(self) -> Literal[False]:
        return False


@final
@dataclass(slots=True, eq=False, frozen=True)
class Failure[T](Result[T]):

    @override
    def success(self) -> Literal[False]:
        return False

    @override
    def failure(self) -> Literal[True]:
        return True


class Job[**ParamTs, SuccessT, FailureT](Processor[ParamTs, Success[SuccessT] | Failure[FailureT]]):

    __slots__ = ("_process", "success_signal", "failure_signal")
    _process: Callable[ParamTs, Coroutine[Any, Any, Success[SuccessT] | Failure[FailureT]]]
    success_signal: Signal[[SuccessT], Any]
    failure_signal: Signal[[FailureT], Any]

    def __init__(self, process: Callable[ParamTs, Coroutine[Any, Any, Success[SuccessT] | Failure[FailureT]]]) -> None:
        super().__init__()
        self._process = process
        self.success_signal = Signal()
        self.failure_signal = Signal()

    @override
    async def process(self, *args: ParamTs.args, **kwargs: ParamTs.kwargs) -> Success[SuccessT] | Failure[FailureT]:
        return await self._process(*args, **kwargs)

    @override
    async def process_executor(self, *args: ParamTs.args, **kwargs: ParamTs.kwargs) -> None:
        result = await self.process(*args, **kwargs)
        if result.success():
            assert isinstance(result, Success)
            self.success_signal.maybe_run(result.value)
        else:
            assert isinstance(result, Failure)
            self.failure_signal.maybe_run(result.value)

    @override
    def run(self, *args: ParamTs.args, **kwargs: ParamTs.kwargs) -> Task[None]:
        if self.running():
            raise RuntimeError("Job is already running")
        return super().run(*args, **kwargs)


class BufferedJob[BufferT, SuccessT, FailureT](Job[[], SuccessT, FailureT]):

    __slots__ = ("_buffer",)
    _buffer: Buffer[BufferT]

    def __init__(
        self,
        process: Callable[[Buffer[BufferT]], Coroutine[Any, Any, Success[SuccessT] | Failure[FailureT]]],
        *,
        buffer: Buffer[BufferT] | None = None,
    ) -> None:
        if buffer is None:
            buffer = Buffer()
        buffer.close()
        super().__init__(functools.partial(process, buffer))
        self._buffer = buffer

    @override
    def _on_task_done(self, task: Task[None]) -> None:
        super()._on_task_done(task)
        self._buffer.clear()
        self._buffer.close()

    @override
    def run(self) -> Task[None]:
        self._buffer.open()
        try:
            return super().run()
        except:
            self._buffer.close()
            raise

    def send(self, value: BufferT, /) -> None:
        self._buffer.send(value)


def job[**ParamTs, SuccessT, FailureT](
    process: Callable[
        ParamTs,
        Coroutine[Any, Any, Success[SuccessT] | Failure[FailureT]],
    ],
) -> Job[ParamTs, SuccessT, FailureT]:
    return Job(process)


def buffered_job[BufferT, SuccessT, FailureT](
    buffer: Buffer[BufferT] | None = None,
) -> Callable[
    [Callable[[Buffer[BufferT]], Coroutine[Any, Any, Success[SuccessT] | Failure[FailureT]]]],
    BufferedJob[BufferT, SuccessT, FailureT],
]:

    def buffered_job_decorator(
        process: Callable[[Buffer[BufferT]], Coroutine[Any, Any, Success[SuccessT] | Failure[FailureT]]],
    ) -> BufferedJob[BufferT, SuccessT, FailureT]:
        return BufferedJob(process, buffer=buffer)

    return buffered_job_decorator
