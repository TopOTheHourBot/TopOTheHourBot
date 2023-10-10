from __future__ import annotations

__all__ = ["run"]

import logging
from asyncio import TaskGroup
from collections.abc import Iterator, Sequence
from typing import Final, Literal, override

from channels import (Channel, LatentChannel, StopRecv, StopSend,
                      SupportsSendAndRecv)
from ircv3 import IRCv3Command, IRCv3CommandProtocol
from ircv3.dialects import twitch
from ircv3.dialects.twitch import ClientPrivmsg, Ping, ServerPrivmsg
from websockets import client
from websockets.client import WebSocketClientProtocol
from websockets.exceptions import ConnectionClosed

from .pipes import Pipe, Transport

URI: Final[str] = "ws://irc-ws.chat.twitch.tv:80"
MESSAGE_DELAY: Final[float] = 1.5


class TwitchSocket(SupportsSendAndRecv[IRCv3CommandProtocol | str, Iterator[IRCv3CommandProtocol]]):

    CRLF: Final[Literal["\r\n"]] = "\r\n"

    __slots__ = ("_socket")
    _socket: WebSocketClientProtocol

    def __init__(self, socket: WebSocketClientProtocol, /) -> None:
        self._socket = socket

    @override
    async def send(self, command: IRCv3CommandProtocol | str) -> None:
        data = str(command)
        try:
            await self._socket.send(data)
        except ConnectionClosed as error:
            logging.exception(error)
            raise StopSend from error

    @override
    async def recv(self) -> Iterator[IRCv3CommandProtocol]:
        try:
            data = await self._socket.recv()
        except ConnectionClosed as error:
            logging.exception(error)
            raise StopRecv from error
        assert isinstance(data, str)
        return self._command_iterator(data)

    def _command_iterator(self, data: str) -> Iterator[IRCv3CommandProtocol]:
        crlf = self.CRLF
        for command in map(
            IRCv3Command.from_string,
            data.rstrip(crlf).split(crlf),
        ):
            name = command.name
            if name == "PRIVMSG":
                yield ServerPrivmsg.cast(command)
            elif name == "PING":
                yield Ping.cast(command)
            else:
                yield command


async def run(
    access_token: str,
    *,
    pipes: Sequence[Pipe[IRCv3CommandProtocol, ClientPrivmsg | str, IRCv3CommandProtocol | str]],
    tags: bool = True,
    user: str = "topothehourbot",
) -> None:
    async for socket in client.connect(URI):
        try:
            if tags:
                await socket.send("CAP REQ :twitch.tv/membership twitch.tv/tags twitch.tv/commands")
            await socket.send(f"PASS oauth:{access_token}")
            await socket.send(f"NICK {user}")
        except ConnectionClosed:
            continue

        omstream = LatentChannel[ClientPrivmsg | str](5)
        osstream = TwitchSocket(socket)

        transports = [
            Transport(
                pipe,
                Channel[IRCv3CommandProtocol](),
                omstream=omstream,
                osstream=osstream,
            )
            for pipe in pipes
        ]

        async with TaskGroup() as tasks:
            tasks.create_task(
                osstream.send_each(
                    omstream.recv_each().stagger(MESSAGE_DELAY),
                ),
            )
            for transport in transports:
                tasks.create_task(transport.open())

            async for commands in osstream:
                for command in commands:
                    if twitch.is_ping(command):
                        tasks.create_task(osstream.try_send(f"PONG :{command.comment}"))
                        continue
                    for transport in transports:
                        tasks.create_task(transport.send(command))
