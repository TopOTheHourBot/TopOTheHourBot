from __future__ import annotations

__all__ = ["Summarizer"]

from abc import ABCMeta, abstractmethod
from asyncio import TaskGroup
from typing import Optional, final

from ircv3 import IRCv3ServerCommandProtocol

from .client import Client
from .localizer import Localizer


class Summarizer[ClientT: Client | Localizer, SummationT, SummandT](metaclass=ABCMeta):
    """A base attachment class for designing map-reduce routines across server
    commands

    Upon ``run()``ning, perpetually executes the map-reduce routine over
    batches of successful command mappings. Batches begin upon the first
    successful mapping, and ends when no further mappings can be performed
    within ``timeout``. At which point, ``finalize()`` is asynchronously
    dispatched with the reduction value, and the map-reduce routine prepares to
    restart for the next batch.

    ``timeout`` can be set to ``None`` to disable repeated executions of the
    routine. ``run()`` guarantees that ``finalize()`` will be called and
    awaited for upon connection closure.
    """

    __slots__ = ("client")
    client: ClientT

    def __init__(self, client: ClientT) -> None:
        self.client = client

    @property
    @abstractmethod
    def initial(self) -> SummationT:
        raise NotImplementedError

    @property
    @abstractmethod
    def timeout(self) -> Optional[float]:
        raise NotImplementedError

    @abstractmethod
    def mapper(self, command: IRCv3ServerCommandProtocol, /) -> Optional[SummandT]:
        raise NotImplementedError

    @abstractmethod
    def reducer(self, summation: SummationT, summand: SummandT, /) -> SummationT:
        raise NotImplementedError

    @abstractmethod
    async def finalizer(self, summation: SummationT, /) -> None:
        raise NotImplementedError

    @final
    async def run(self) -> None:
        async with TaskGroup() as tasks:
            with self.client.attachment() as pipe:
                while (
                    reduction := await aiter(pipe)
                        .map(self.mapper)
                        .not_none()
                        .timeout(self.timeout)
                        .reduce(self.initial, self.reducer)
                ):
                    tasks.create_task(self.finalizer(reduction.value))
