from __future__ import annotations

import logging
from asyncio import TaskGroup
from typing import Self

from websockets import client
from websockets.exceptions import ConnectionClosed

from .ircv3 import IRCv3Package
from .streams import OStreamBase, TimeboundIRCv3IOStream


class IRCv3Client:

    __slots__ = ("_uri", "_cooldown", "_streams")
    _uri: str
    _cooldown: float
    _streams: list[OStreamBase[IRCv3Package]]

    def __init__(self, uri: str, *, cooldown: float = 1.5) -> None:
        self._uri = uri
        self._cooldown = cooldown
        self._streams = []

    @property
    def uri(self) -> str:
        return self._uri

    @property
    def cooldown(self) -> float:
        return self._cooldown

    def subscribe(self, stream: OStreamBase[IRCv3Package]) -> Self:
        self._streams.append(stream)
        return self

    async def drain(self) -> None:
        async for socket in client.connect(self._uri):
            cooldown = self._cooldown
            irc_stream = TimeboundIRCv3IOStream(
                socket=socket,
                cooldown=cooldown,
            )
            try:
                streams = self._streams
                async with TaskGroup() as tg:
                    for stream in streams:
                        tg.create_task(stream.drain(irc_stream))  # TODO: abstract drain() method added to
                    async for package in irc_stream.get_each():   # the interface (Pipe?)
                        for stream in streams:
                            tg.create_task(stream.put(package))
            except* ConnectionClosed as exc:
                logging.exception(exc)
                continue
