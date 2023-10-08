from __future__ import annotations

import logging
from asyncio import TaskGroup
from typing import Final

from channels import (Channel, LatentChannel, StopRecv, StopSend,
                      SupportsRecvAndSend)
from ircv3 import IRCv3Command, IRCv3CommandProtocol
from ircv3.dialects.twitch import ServerPrivmsg
from websockets import client
from websockets.client import WebSocketClientProtocol
from websockets.exceptions import ConnectionClosed

from .plumbing import Pipe, Transport

URI: Final[str] = "ws://irc-ws.chat.twitch.tv:80"

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


class IRCv3Channel(SupportsRecvAndSend[IRCv3CommandProtocol, IRCv3CommandProtocol | str]):

    __slots__ = ("_socket")
    _socket: WebSocketClientProtocol

    def __init__(self, socket: WebSocketClientProtocol, /) -> None:
        self._socket = socket

    async def recv(self) -> IRCv3CommandProtocol:
        try:
            data = await self._socket.recv()
        except ConnectionClosed as error:
            logging.exception(error)
            raise StopRecv from error
        assert isinstance(data, str)
        command = IRCv3Command.from_string(data)
        if command.name == "PRIVMSG":
            return ServerPrivmsg.cast(command)
        return command

    async def send(self, command: IRCv3CommandProtocol | str) -> None:
        data = str(command)
        try:
            await self._socket.send(data)
        except ConnectionClosed as error:
            logging.exception(error)
            raise StopSend from error


async def main(
    access_token: str,
    *pipes: Pipe[IRCv3CommandProtocol, IRCv3CommandProtocol | str],
    request_tags: bool = True,
) -> None:

    writer_stream = LatentChannel[IRCv3CommandProtocol | str](capacity=4)
    transports = [
        Transport(pipe, iostream=Channel[IRCv3CommandProtocol](), ostream=writer_stream)
        for pipe in pipes
    ]

    async for socket in client.connect(URI):
        socket_stream = IRCv3Channel(socket)
        try:
            if request_tags:
                await socket_stream.send("CAP REQ :twitch.tv/membership twitch.tv/tags twitch.tv/commands")
            await socket_stream.send("PASS oauth:" + access_token)
            await socket_stream.send("NICK topothehourbot")
        except StopSend:
            continue

        async with TaskGroup() as tasks:
            tasks.create_task(
                socket_stream.send_each(
                    writer_stream
                        .recv_each()
                        .stagger(WRITE_DELAY),
                ),
            )
            for transport in transports:
                tasks.create_task(transport.ready())

            commands = socket_stream.recv_each()
            async for command in commands:
                for transport in transports:
                    tasks.create_task(transport.send(command))
