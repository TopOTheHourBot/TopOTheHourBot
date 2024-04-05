from __future__ import annotations

__all__ = ["Client", "Channel"]

import asyncio
from collections import defaultdict
from typing import ClassVar

from ircv3.dialects.twitch import (ClientJoin, ClientMessage, ClientPart,
                                   ServerMessage)
from websockets import WebSocketClientProtocol


class Client:

    # These are strictly accessed as class variables to ensure that, no matter
    # the instance, all will be working with the same cooldowns and epochs.

    _message_cooldowns: ClassVar[defaultdict[str, float]] = defaultdict(lambda: 1.5)
    """A mapping of client names to their respective PRIVMSG cooldowns

    Defaults to 1.5 seconds, allowing 20 messages to be sent every 30 seconds
    (the standard Twitch rate limit).
    """
    _join_cooldowns: ClassVar[defaultdict[str, float]] = defaultdict(lambda: 1.5)
    """A mapping of client names to their respective JOIN cooldowns

    Defaults to 1.5 seconds, allowing 20 joins to be sent every 30 seconds (the
    standard Twitch rate limit).
    """
    _last_message_epochs: ClassVar[defaultdict[str, float]] = defaultdict(lambda: 0)
    """A mapping of client names to the times at which they last sent a PRIVMSG

    Set to 0 if the client has not sent a PRIVMSG.
    """
    _last_join_epochs: ClassVar[defaultdict[str, float]] = defaultdict(lambda: 0)
    """A mapping of client names to the times at which they last sent a JOIN

    Set to 0 if the client has not sent a JOIN.
    """

    __slots__ = ("_channels", "websocket", "name")
    _channels: dict[str, Channel]
    websocket: WebSocketClientProtocol
    name: str

    def __init__(self, websocket: WebSocketClientProtocol, *, name: str) -> None:
        super().__init__()
        self._channels = {}
        self.websocket = websocket
        self.name = name

    @property
    def message_cooldown(self) -> float:
        """The client's PRIVMSG cooldown, in seconds

        Defaults to 1.5, allowing 20 messages to be sent every 30 seconds (the
        standard rate limit).

        Note that setting this property will modify the message cooldown for
        all ``Client`` instances of the same name.
        """
        return Client._message_cooldowns[self.name]

    @message_cooldown.setter
    def message_cooldown(self, cooldown: float) -> None:
        Client._message_cooldowns[self.name] = cooldown

    @property
    def join_cooldown(self) -> float:
        """The client's JOIN cooldown, in seconds

        Defaults to 1.5, allowing 20 joins to be sent every 30 seconds (the
        standard rate limit).

        Note that setting this property will modify the join cooldown for all
        ``Client`` instances of the same name.
        """
        return Client._join_cooldowns[self.name]

    @join_cooldown.setter
    def join_cooldown(self, cooldown: float) -> None:
        Client._join_cooldowns[self.name] = cooldown

    @property
    def last_message_epoch(self) -> float:
        """The time at which the last PRIVMSG was sent, respective to the
        running event loop

        Set to 0 if the client has not sent a PRIVMSG.
        """
        return Client._last_message_epochs[self.name]

    @property
    def last_join_epoch(self) -> float:
        """The time at which the last JOIN was sent, respective to the running
        event loop

        Set to 0 if the client has not sent a JOIN.
        """
        return Client._last_join_epochs[self.name]

    @property
    def latency(self) -> float:
        """The websocket latency, in milliseconds

        Set to 0 if the websocket has not sent a ping.
        """
        return self.websocket.latency * 1000

    def channel(self, name: str) -> Channel:
        channels = self._channels
        try:
            return channels[name]
        except KeyError:
            channel = Channel(self, name=name)
            channels[name] = channel
            return channel

    async def send(self, command: object, /) -> None:
        data = str(command)
        await self.websocket.send(data)

    async def message(
        self,
        comment: object,
        target: ServerMessage | str,
        *,
        important: bool = True,
    ) -> None:
        name = self.name
        curr_message_epoch = asyncio.get_running_loop().time()
        last_message_epoch = Client._last_message_epochs[name]
        if last_message_epoch:
            delay = max(
                Client._message_cooldowns[name]
                - (curr_message_epoch - last_message_epoch),
                0,
            )
        else:
            delay = 0
        if important:
            Client._last_message_epochs[name] = curr_message_epoch + delay
            if delay:
                await asyncio.sleep(delay)
        else:
            if delay:
                return
            Client._last_message_epochs[name] = curr_message_epoch
        comment = str(comment)
        command = ClientMessage(target, comment) if isinstance(target, str) else target.reply(comment)
        return await self.send(command)

    async def join(self, *rooms: str) -> None:
        name = self.name
        curr_join_epoch = asyncio.get_running_loop().time()
        last_join_epoch = Client._last_join_epochs[name]
        if last_join_epoch:
            delay = max(
                Client._join_cooldowns[name]
                - (curr_join_epoch - last_join_epoch),
                0,
            )
        else:
            delay = 0
        Client._last_join_epochs[name] = curr_join_epoch + delay
        if delay:
            await asyncio.sleep(delay)
        return await self.send(ClientJoin(*rooms))

    async def part(self, *rooms: str) -> None:
        return await self.send(ClientPart(*rooms))

    async def close(self) -> None:
        await self.websocket.close()


class Channel:

    __slots__ = ("client", "name", "room")
    client: Client
    name: str
    room: str

    def __init__(self, client: Client, *, name: str) -> None:
        super().__init__()
        self.client = client
        self.name = name
        self.room = "#" + name

    async def message(
        self,
        comment: object,
        target: ServerMessage | str = "#",
        *,
        important: bool = True,
    ) -> None:
        await self.client.message(
            comment,
            self.room if target == "#" else target,
            important=important,
        )
