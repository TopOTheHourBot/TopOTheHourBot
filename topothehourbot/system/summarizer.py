from __future__ import annotations

__all__ = ["Summarizer"]

from abc import ABCMeta, abstractmethod
from asyncio import TaskGroup
from typing import Any, Optional, final

from ircv3 import IRCv3ServerCommandProtocol

from .client import Client
from .sub_client import SubClient

type SourceClient = Client | SubClient


class Summarizer[
    SourceClientT: SourceClient,
    SummationT,
    SummandT,
](metaclass=ABCMeta):
    """A base attachment class for designing map-reduce routines across server
    commands

    Upon ``run()``ning, perpetually executes the map-reduce routine over
    batches of successful command mappings. Batches begin upon the first
    successful mapping, and end when no further mappings can be performed
    within ``timeout``. At which point, ``finalize()`` is asynchronously
    dispatched with the reduction value, and the map-reduce routine prepares to
    restart for the next batch.

    ``timeout`` can be set to ``None`` to disable repeated executions of the
    routine. ``run()`` guarantees that ``finalize()`` will be called and
    awaited for upon connection closure.
    """

    __slots__ = ("source_client")
    source_client: SourceClientT

    def __init__(self, source_client: SourceClientT) -> None:
        self.source_client = source_client

    @property
    @abstractmethod
    def initial(self) -> SummationT:
        """The initial reduction value

        Typically a kind of nil value with respect to the data type.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def timeout(self) -> Optional[float]:
        """The mapping timeout, in seconds

        A batch ends when no mappings can be performed within this duration,
        beginning from the latest successful mapping.
        """
        raise NotImplementedError

    @abstractmethod
    def mapper(self, value: IRCv3ServerCommandProtocol | Any, /) -> Optional[SummandT]:
        """Return ``command`` as a summand, or ``None`` if no such conversion
        is possible
        """
        raise NotImplementedError

    @abstractmethod
    def reducer(self, summation: SummationT, summand: SummandT, /) -> SummationT:
        """Return ``summation`` and ``summand`` reduced to a new summation"""
        raise NotImplementedError

    def predicator(self, summation: SummationT, /) -> object:
        """Return true if ``summation`` should be finalized, otherwise false

        Unconditionally returns true in the base implementation.
        """
        return True

    @abstractmethod
    async def finalizer(self, summation: SummationT, /) -> None:
        """Finalize the routine

        Often reports ``summation`` to the client or a storage system.
        """
        raise NotImplementedError

    @final
    async def run(self) -> None:
        """Perpetually read and perform the map-reduce routine with attachment
        to the client
        """
        async with TaskGroup() as tasks:
            with self.source_client.attachment() as pipe:
                while (
                    reduction := await aiter(pipe)
                        .map(self.mapper)
                        .not_none()
                        .timeout(self.timeout)
                        .reduce(self.initial, self.reducer)
                ):
                    if self.predicator(summation := reduction.value):
                        tasks.create_task(self.finalizer(summation))
