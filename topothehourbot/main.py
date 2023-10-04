from __future__ import annotations

import logging
from asyncio import TaskGroup
from typing import Final, Literal

from channels import Channel, RecvError, SendError, SupportsRecvAndSend
from ircv3 import IRCv3Command
from websockets import client
from websockets.client import WebSocketClientProtocol
from websockets.exceptions import ConnectionClosed

from .pipe import Pipe

URI: Final[Literal["ws://irc-ws.chat.twitch.tv:80"]] = "ws://irc-ws.chat.twitch.tv:80"

ACCESS_TOKEN: Final[str]  # These will likely be imports (from toml?) in the future
CLIENT_SECRET: Final[str]

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
OUTGOING_DELAY: Final[float] = 1.5


class IRCv3Channel(SupportsRecvAndSend[IRCv3Command, IRCv3Command | str]):

    __slots__ = ("_socket")
    _socket: WebSocketClientProtocol

    def __init__(self, socket: WebSocketClientProtocol, /) -> None:
        self._socket = socket

    async def recv(self) -> IRCv3Command:
        try:
            data = await self._socket.recv()
        except ConnectionClosed as error:
            logging.exception(error)
            raise RecvError from error
        else:
            assert isinstance(data, str)
            return IRCv3Command.from_string(data)

    async def send(self, command: IRCv3Command | str) -> None:
        data = str(command)
        try:
            await self._socket.send(data)
        except ConnectionClosed as error:
            logging.exception(error)
            raise SendError from error


async def main(*pipes: Pipe) -> None:

    reader_streams = [Channel[IRCv3Command]() for _ in range(len(pipes))]
    writer_stream = Channel[IRCv3Command]()

    async with TaskGroup() as tasks:

        for pipe, reader_stream in zip(pipes, reader_streams):
            tasks.create_task(pipe(reader_stream, writer_stream))

        async for socket in client.connect(URI):
            socket_stream = IRCv3Channel(socket)
            tasks.create_task(
                socket_stream.send_each(
                    writer_stream.recv_each().stagger(OUTGOING_DELAY),
                ),
            )

            await socket_stream.send("CAP REQ :twitch.tv/membership twitch.tv/tags twitch.tv/commands")
            await socket_stream.send("PASS oauth:" + ACCESS_TOKEN)
            await socket_stream.send("NICK topothehourbot")

            commands = socket_stream.recv_each()
            async for command in commands:
                for reader_stream in reader_streams:
                    tasks.create_task(reader_stream.send(command))
