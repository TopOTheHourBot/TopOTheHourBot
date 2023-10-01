from __future__ import annotations

__all__ = ["TaskManager"]

import asyncio
from asyncio import Task
from collections.abc import Coroutine, Generator
from typing import Any, Optional, TypeAlias, TypeVar

T = TypeVar("T")

CoroutineLike: TypeAlias = Generator[Any, None, T] | Coroutine[Any, Any, T]


class TaskManager:

    __slots__ = ("_tasks")
    _tasks: set[Task]

    def __init__(self) -> None:
        self._tasks = set()

    def create_task(self, coro: CoroutineLike[T], *, name: Optional[str] = None) -> Task[T]:
        task = asyncio.create_task(coro, name=name)
        task.add_done_callback(self._tasks.discard)
        self._tasks.add(task)
        return task

    def cancel(self) -> None:
        for task in self._tasks:
            if not task.done():
                task.cancel()
