from __future__ import annotations

import logging
from abc import ABCMeta, abstractmethod
from asyncio import TaskGroup
from collections.abc import AsyncIterator, Iterable, Sequence
from typing import Final, Generic, Optional, Self, TypeVar, final

from websockets import client
from websockets.exceptions import ConnectionClosed

from .ircv3 import IRCv3Package
from .streams import (IOStreamBase, OStreamBase, TimeboundIOStreamWrapper,
                      TimeboundIRCv3IOStream, UnboundIOStream)

ValueT = TypeVar("ValueT")


class Query(IOStreamBase[IRCv3Package, IRCv3Package], Generic[ValueT], metaclass=ABCMeta):

    __slots__ = ("_stream")
    _stream: UnboundIOStream[IRCv3Package]

    def __init__(self) -> None:
        self._stream = UnboundIOStream()

    @abstractmethod
    def values(self) -> AsyncIterator[ValueT]:
        raise NotImplementedError

    @abstractmethod
    def finalize(self, value: ValueT, /) -> Optional[object]:
        raise NotImplementedError

    @final
    async def get(self) -> IRCv3Package:
        return await self._stream.get()

    @final
    async def put(self, package: IRCv3Package) -> None:
        await self._stream.put(package)

    @final
    async def drain(self, ostream: OStreamBase[object], /) -> None:
        async for value in self.values():
            result = self.finalize(value)
            if result is None:
                continue
            await ostream.put(result)


class Channel(IOStreamBase[IRCv3Package, IRCv3Package]):

    __slots__ = ("_name", "_queries", "_cooldown", "_stream")
    _name: str
    _queries: list[Query]
    _cooldown: float
    _stream: UnboundIOStream[IRCv3Package]

    def __init__(self, name: str, *, queries: Iterable[Query] = (), cooldown: float = 0) -> None:
        self._name = name if name.startswith("#") else f"#{name}"
        self._queries = list(queries)
        self._cooldown = cooldown
        self._stream = UnboundIOStream()

    @property
    def name(self) -> str:
        return self._name

    @property
    def queries(self) -> Sequence[Query]:
        return self._queries

    @property
    def cooldown(self) -> float:
        return self._cooldown

    def register_query(self, query: Query) -> Self:
        self._queries.append(query)
        return self

    @final
    async def get(self) -> IRCv3Package:
        return await self._stream.get()

    @final
    async def put(self, package: IRCv3Package) -> None:
        await self._stream.put(package)

    @final
    async def drain(self, ostream: OStreamBase[object], /) -> None:
        return  # TODO: need TimeboundOStreamWrapper


class Client:

    URI: Final[str] = "ws://irc-ws.chat.twitch.tv:80"

    __slots__ = ("_user", "_auth_token", "_channels", "_cooldown")
    _user: str
    _auth_token: str
    _channels: list[Channel]
    _cooldown: float

    def __init__(
        self,
        user: str,
        auth_token: str,
        *,
        channels: Iterable[Channel] = (),
        cooldown: float = 1.5,
    ) -> None:
        self._user = user
        self._auth_token = auth_token
        self._channels = list(channels)
        self._cooldown = cooldown

    @property
    def user(self) -> str:
        return self._user

    @property
    def auth_token(self) -> str:
        return self._auth_token

    @property
    def channels(self) -> Sequence[Channel]:
        return self._channels

    @property
    def cooldown(self) -> float:
        return self._cooldown

    def register_channel(self, channel: Channel) -> Self:
        self._channels.append(channel)
        return self

    async def drain(self) -> None:
        channels = self._channels
        cooldown = self._cooldown
        async for socket in client.connect(self.URI):
            stream = TimeboundIRCv3IOStream(socket)
            try:
                await stream.put("CAP REQ :twitch.tv/membership twitch.tv/tags twitch.tv/commands")
                await stream.put(f"PASS oauth:{self._auth_token}")
                await stream.put(f"NICK {self._user}")
                stream.cooldown = cooldown  # We're okay to pass credentials without cooldown
                async with TaskGroup() as task_group:
                    for channel in channels:
                        task_group.create_task(channel.drain(stream))
                    async for package in stream.get_each():
                        for channel in channels:
                            await channel.put(package)
            except* ConnectionClosed as exc:
                logging.exception(exc)
                continue
