from __future__ import annotations

__all__ = ["CallbackReturn", "Callback", "Signal"]

import asyncio
import logging
from asyncio import CancelledError, Task
from collections.abc import Callable, Coroutine, Iterator
from contextlib import AbstractContextManager, contextmanager
from typing import Any, Literal, Self, overload, override

from .processor import Processor

type CallbackReturn = Coroutine[Any, Any, None] | None
type Callback[**ParamTs] = Callable[ParamTs, CallbackReturn]


class Signal[**ParamTs](Processor[ParamTs, None]):

    __slots__ = ("_callbacks", "timeout")
    _callbacks: set[Callback[ParamTs]]
    timeout: float | None

    def __init__(self, timeout: float | None = None) -> None:
        super().__init__()
        self._callbacks = set()
        self.timeout = timeout

    @override
    async def process(self, *args: ParamTs.args, **kwargs: ParamTs.kwargs) -> None:
        """Dispatch all callbacks as a task and await their returns"""
        loop = asyncio.get_running_loop()

        tasks = list[Task[None]]()
        for callback in self._callbacks:
            coro = callback(*args, **kwargs)
            if coro is None:
                continue
            task = loop.create_task(coro)
            tasks.append(task)

        if not tasks:
            return

        for waiter in asyncio.as_completed(tasks, timeout=self.timeout):
            try:
                await waiter
            except CancelledError:
                for task in tasks:
                    task.cancel()
                raise
            except TimeoutError:
                logging.exception("Signal process timed out")
            except Exception:
                logging.exception("Callback excepted during Signal processing")

    def callback(self, callback: Callback[ParamTs]) -> Callback[ParamTs]:
        """Decorate a callback to schedule upon the signal's emission"""
        self.add_callback(callback)
        return callback

    @contextmanager
    def _add_callback_manager(self, callback: Callback[ParamTs]) -> Iterator[Self]:
        try:
            yield self
        finally:
            self.remove_callback(callback, temporary=False)

    @overload
    def add_callback(
        self,
        callback: Callback[ParamTs],
        *,
        temporary: Literal[True],
    ) -> AbstractContextManager[Self]: ...
    @overload
    def add_callback(
        self,
        callback: Callback[ParamTs],
        *,
        temporary: Literal[False],
    ) -> Self: ...
    @overload
    def add_callback(
        self,
        callback: Callback[ParamTs],
    ) -> Self: ...

    def add_callback(
        self,
        callback: Callback[ParamTs],
        *,
        temporary: bool = False,
    ) -> Self | AbstractContextManager[Self]:
        """Add a callback to schedule upon the signal's emission

        If ``temporary``, return a context manager that removes the callback
        upon exit.
        """
        self._callbacks.add(callback)
        if temporary:
            return self._add_callback_manager(callback)
        return self

    @contextmanager
    def _remove_callback_manager(self, callback: Callback[ParamTs]) -> Iterator[Self]:
        try:
            yield self
        finally:
            self.add_callback(callback, temporary=False)

    @overload
    def remove_callback(
        self,
        callback: Callback[ParamTs],
        *,
        temporary: Literal[True],
    ) -> AbstractContextManager[Self]: ...
    @overload
    def remove_callback(
        self,
        callback: Callback[ParamTs],
        *,
        temporary: Literal[False],
    ) -> Self: ...
    @overload
    def remove_callback(
        self,
        callback: Callback[ParamTs],
    ) -> Self: ...

    def remove_callback(
        self,
        callback: Callback[ParamTs],
        *,
        temporary: bool = False,
    ) -> Self | AbstractContextManager[Self]:
        """Remove a callback to schedule upon the signal's emission

        If ``temporary``, return a context manager that adds the callback upon
        exit.
        """
        self._callbacks.discard(callback)
        if temporary:
            return self._remove_callback_manager(callback)
        return self

    def maybe_run(self, *args: ParamTs.args, **kwargs: ParamTs.kwargs) -> Task[None] | None:
        """Schedule ``process()`` as a task if containing at least one
        callback, otherwise do nothing
        """
        if not self._callbacks:
            return
        return self.run(*args, **kwargs)
