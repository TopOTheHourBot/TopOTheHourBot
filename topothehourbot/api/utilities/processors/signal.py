from __future__ import annotations

__all__ = ["Signal"]

import asyncio
import logging
from asyncio import CancelledError, Task
from collections.abc import Callable, Coroutine, Iterator
from contextlib import contextmanager
from typing import Any, Self, override

from .processor import Processor


class Signal[**ParamTs, ResultT](Processor[ParamTs, None]):

    __slots__ = ("_callbacks", "timeout")
    _callbacks: set[Callable[ParamTs, Coroutine[Any, Any, ResultT]]]
    timeout: float | None

    def __init__(self, timeout: float | None = None) -> None:
        super().__init__()
        self._callbacks = set()
        self.timeout = timeout

    @override
    async def process(self, *args: ParamTs.args, **kwargs: ParamTs.kwargs) -> None:
        """Dispatch all callbacks as a task and await their returns"""
        loop = asyncio.get_running_loop()
        timeout = self.timeout

        coros: Iterator[Coroutine[Any, Any, ResultT]]
        if timeout is not None and timeout > 0:
            coros = (
                asyncio.wait_for(
                    callback(*args, **kwargs),
                    timeout=timeout,
                )
                for callback in self._callbacks
            )  # type: ignore
        else:
            coros = (
                callback(*args, **kwargs)
                for callback in self._callbacks
            )

        tasks = set[Task[ResultT]]()
        for coro in coros:
            task = loop.create_task(coro)
            tasks.add(task)

        for waiter in asyncio.as_completed(tasks):
            try:
                result = await waiter
            except CancelledError:
                for task in tasks:
                    task.cancel()
                raise
            except TimeoutError:
                logging.exception("Callback timed out during Signal processing")
            except Exception:
                logging.exception("Callback excepted during Signal processing")
            else:
                if result is None:
                    continue
                logging.info(f"Callback finished normally with result, {result!r}")

    def callback(self, callback: Callable[ParamTs, Coroutine[Any, Any, ResultT]]) -> Callable[ParamTs, Coroutine[Any, Any, ResultT]]:
        """Decorate a callback to schedule upon the signal's emission"""
        self.add_callback(callback)
        return callback

    @contextmanager
    def continuation(self, callback: Callable[ParamTs, Coroutine[Any, Any, ResultT]]) -> Iterator[Self]:
        """Return a context manager that adds and removes a callback upon enter
        and exit, respectively
        """
        self.add_callback(callback)
        try:
            yield self
        finally:
            self.remove_callback(callback)

    @contextmanager
    def suspension(self, callback: Callable[ParamTs, Coroutine[Any, Any, ResultT]]) -> Iterator[Self]:
        """Return a context manager that removes and adds a callback upon enter
        and exit, respectively
        """
        self.remove_callback(callback)
        try:
            yield self
        finally:
            self.add_callback(callback)

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
