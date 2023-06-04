from __future__ import annotations

import asyncio
from asyncio import Task
from collections.abc import Coroutine, Generator
from contextvars import Context
from typing import Any, Optional, TypeAlias, TypeVar

__all__ = ["TaskManager"]

T = TypeVar("T")

CoroutineLike: TypeAlias = Generator[Any, None, T] | Coroutine[Any, Any, T]


class TaskManager:

    __slots__ = ("_tasks")

    _tasks: set[Task]

    def __init__(self) -> None:
        self._tasks = set()

    def create_task(
        self,
        coro: CoroutineLike[T],
        *,
        name: Optional[str] = None,
        context: Optional[Context] = None,
    ) -> Task[T]:
        """Create, schedule, and return a task from ``coro``

        Tasks constructed by this method are internally put into a collection
        and set to be removed from it when finished. Thus, maintaining
        references to resultant task objects is unnecessary.
        """
        task = asyncio.create_task(coro, name=name, context=context)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    async def cancel(self) -> None:
        """Cancel all enrolled tasks and await their garbage collection"""
        for task in self._tasks:
            task.cancel()
        while self._tasks:
            await asyncio.sleep(0)
