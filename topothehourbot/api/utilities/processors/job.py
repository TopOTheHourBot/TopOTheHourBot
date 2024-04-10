from __future__ import annotations

__all__ = ["Job", "job"]

from asyncio import Task
from collections.abc import Callable, Coroutine
from typing import Any, override

from .processor import Processor


class Job[**ParamTs, ResultT](Processor[ParamTs, ResultT]):

    __slots__ = ("_process",)
    _process: Callable[ParamTs, Coroutine[Any, Any, ResultT]]

    def __init__(self, process: Callable[ParamTs, Coroutine[Any, Any, ResultT]]) -> None:
        super().__init__()
        self._process = process

    @override
    async def process(self, *args: ParamTs.args, **kwargs: ParamTs.kwargs) -> ResultT:
        return await self._process(*args, **kwargs)

    @override
    def run(self, *args: ParamTs.args, **kwargs: ParamTs.kwargs) -> Task[ResultT]:
        if self.running():
            raise RuntimeError("Job is already running")
        return super().run(*args, **kwargs)


def job[**ParamTs, ResultT](process: Callable[ParamTs, Coroutine[Any, Any, ResultT]]) -> Job[ParamTs, ResultT]:
    return Job(process)
