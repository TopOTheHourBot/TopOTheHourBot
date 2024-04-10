from __future__ import annotations

__all__ = ["Processor"]

import asyncio
from abc import ABCMeta, abstractmethod
from asyncio import Task


class Processor[**ParamTs, ResultT](metaclass=ABCMeta):

    __slots__ = ("_tasks",)
    _tasks: set[Task[ResultT]]

    def __init__(self) -> None:
        self._tasks = set()

    def _on_task_done(self, task: Task[ResultT]) -> None:
        self._tasks.discard(task)

    @abstractmethod
    async def process(self, *args: ParamTs.args, **kwargs: ParamTs.kwargs) -> ResultT:
        """The procedure to execute"""
        raise NotImplementedError

    def run(self, *args: ParamTs.args, **kwargs: ParamTs.kwargs) -> Task[ResultT]:
        """Run ``process()`` as a task"""
        task = asyncio.create_task(self.process(*args, **kwargs))
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
