import asyncio
from asyncio import Queue, TimeoutError
from collections.abc import AsyncIterable, AsyncIterator
from typing import Optional, TypeVar

T = TypeVar("T")


class TimeoutQueue(Queue[T]):

    __slots__ = ()

    async def get(self, *, timeout: Optional[float] = None) -> T:
        return await asyncio.wait_for(super().get(), timeout=timeout)

    async def put(self, item: T, *, timeout: Optional[float] = None) -> None:
        await asyncio.wait_for(super().put(item), timeout=timeout)

    async def consume(self, *, timeout: Optional[float] = None) -> AsyncIterator[T]:
        while True:
            try:
                item = await self.get(timeout=timeout)
            except TimeoutError:
                return
            else:
                yield item
                self.task_done()


async def aenumerate(aiterable: AsyncIterable[T], start: int = 0) -> AsyncIterator[tuple[int, T]]:
    i = start
    async for item in aiterable:
        yield i, item
        i += 1
