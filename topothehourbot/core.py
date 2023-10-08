from __future__ import annotations

__all__ = ["run"]

import logging
from asyncio import TaskGroup
from collections.abc import Iterator, Sequence
from typing import Final, Literal

from channels import (Channel, LatentChannel, StopRecv, StopSend,
                      SupportsSendAndRecv)
from ircv3 import IRCv3Command, IRCv3CommandProtocol
from ircv3.dialects.twitch import ServerPrivmsg
from websockets import client
from websockets.client import WebSocketClientProtocol
from websockets.exceptions import ConnectionClosed

from .plumbing import Pipe, Transport

URI: Final[str] = "ws://irc-ws.chat.twitch.tv:80"

CRLF: Final[Literal["\r\n"]] = "\r\n"

# The amount of time, in seconds, to delay before sending subsequent messages
# to the Twitch IRC server.
# This is necessary to avoid exceeding the server's rate limits. If the client
# is not the broadcaster or a moderator of a chat room, the rate limit is 20
# messages every 30 seconds.
# A blanket messaging delay works well to solve this problem - no need to get
# fancier. We solve 20m * Xs/m = 30s for X, which is 1.5s/m (i.e. 1.5 seconds
# for every 1 message).
# The one drawback to this methodology is that our client won't be able to
# "spam" at a very fast rate, but we don't really have a need to.
WRITE_DELAY: Final[float] = 1.5


class TwitchSocket(SupportsSendAndRecv[IRCv3CommandProtocol | str, Iterator[IRCv3CommandProtocol]]):

    __slots__ = ("_socket")
    _socket: WebSocketClientProtocol

    def __init__(self, socket: WebSocketClientProtocol, /) -> None:
        self._socket = socket

    async def send(self, command: IRCv3CommandProtocol | str) -> None:
        data = str(command)
        try:
            await self._socket.send(data)
        except ConnectionClosed as error:
            logging.exception(error)
            raise StopSend from error

    async def recv(self) -> Iterator[IRCv3CommandProtocol]:
        try:
            data = await self._socket.recv()
        except ConnectionClosed as error:
            logging.exception(error)
            raise StopRecv from error
        assert isinstance(data, str)
        return self._command_iterator(data)

    def _command_iterator(self, data: str) -> Iterator[IRCv3CommandProtocol]:
        strings = data.rstrip(CRLF).split(CRLF)
        for command in map(IRCv3Command.from_string, strings):
            if command.name == "PRIVMSG":
                yield ServerPrivmsg.cast(command)
            else:
                yield command


async def run(
    access_token: str,
    *,
    pipes: Sequence[Pipe],
    tags: bool = True,
    user: str = "topothehourbot",
) -> None:
    async for socket in client.connect(URI):
        try:
            if tags:
                await socket.send("CAP REQ :twitch.tv/membership twitch.tv/tags twitch.tv/commands")
            await socket.send(f"PASS oauth:{access_token}")
            await socket.send(f"NICK {user}")
        except StopSend:
            continue

        omstream = LatentChannel[IRCv3CommandProtocol | str](5)
        osstream = TwitchSocket(socket)

        transports = [
            Transport(
                pipe,
                iostream=Channel[IRCv3CommandProtocol](),
                omstream=omstream,
                osstream=osstream,
            )
            for pipe in pipes
        ]

        async with TaskGroup() as tasks:
            tasks.create_task(
                osstream.send_each(
                    omstream.recv_each().stagger(WRITE_DELAY),
                ),
            )
            for transport in transports:
                tasks.create_task(transport.open())

            async for commands in osstream:
                for command in commands:
                    if command.name == "PING":
                        tasks.create_task(osstream.send(f"PONG :{command.comment}"))  # TODO: Handle possible exception
                        continue
                    for transport in transports:
                        tasks.create_task(transport.send(command))
