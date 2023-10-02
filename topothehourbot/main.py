from __future__ import annotations

from asyncio import TaskGroup
from typing import Final

from channels import (Channel, RecvError, SendError, SupportsRecv,
                      SupportsRecvAndSend, SupportsSend)
from ircv3 import IRCv3Command
from websockets import client
from websockets.client import WebSocketClientProtocol
from websockets.exceptions import ConnectionClosed

from .pipe import Pipe

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


class IRCv3Channel(SupportsRecvAndSend[IRCv3Command, IRCv3Command]):

    __slots__ = ("_socket")
    _socket: WebSocketClientProtocol

    def __init__(self, socket: WebSocketClientProtocol, /) -> None:
        self._socket = socket

    async def recv(self) -> IRCv3Command:
        try:
            data = await self._socket.recv()
        except ConnectionClosed as error:
            raise RecvError from error
        else:
            assert isinstance(data, str)
            return IRCv3Command.from_string(data)

    async def send(self, command: IRCv3Command) -> None:
        data = command.to_string()
        try:
            await self._socket.send(data)
        except ConnectionClosed as error:
            raise SendError from error


async def main(*pipes: Pipe) -> None:

    async def sink(
        istream: SupportsRecv[IRCv3Command],
        ostream: SupportsSend[IRCv3Command],
    ) -> None:
        commands = (
            istream
                .recv_each()
                .stagger(OUTGOING_DELAY)
        )
        await ostream.send_each(commands)

    async for socket in client.connect(""):

        reader_streams: list[Channel[IRCv3Command]] = []
        writer_stream = Channel[IRCv3Command]()
        socket_stream = IRCv3Channel(socket)

        # TODO: Send auth, tags request commands (here?)

        async with TaskGroup() as tasks:
            tasks.create_task(sink(writer_stream, socket_stream))

            for pipe in pipes:
                reader_stream = Channel()
                reader_streams.append(reader_stream)
                tasks.create_task(pipe(reader_stream, writer_stream))

            commands = socket_stream.recv_each()
            async for command in commands:
                for reader_stream in reader_streams:
                    tasks.create_task(reader_stream.send(command))
