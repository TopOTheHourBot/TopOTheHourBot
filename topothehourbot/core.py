from __future__ import annotations

__all__ = ["run"]

from asyncio import TaskGroup
from collections.abc import Sequence
from typing import Final

import aiosqlite as sqlite
from channels import Channel, LatentChannel
from ircv3 import IRCv3CommandProtocol
from ircv3.dialects import twitch
from ircv3.dialects.twitch import ClientPrivmsg
from websockets import client
from websockets.exceptions import ConnectionClosed

from .channels import SQLiteChannel, TwitchChannel
from .pipes import Pipe, Transport

URI: Final[str] = "ws://irc-ws.chat.twitch.tv:80"
MESSAGE_DELAY: Final[float] = 1.5


async def run(  # TODO: In desperate need of clean-up (way too much nesting)
    access_token: str,
    *,
    pipes: Sequence[Pipe[IRCv3CommandProtocol, ClientPrivmsg | str, IRCv3CommandProtocol | str]],
    tags: bool = True,
    user: str = "topothehourbot",
) -> None:
    async with sqlite.connect("topothehourbot.db", autocommit=True) as connection:

        async for socket in client.connect(URI):
            try:
                if tags:
                    await socket.send("CAP REQ :twitch.tv/membership twitch.tv/tags twitch.tv/commands")
                await socket.send(f"PASS oauth:{access_token}")
                await socket.send(f"NICK {user}")
            except ConnectionClosed:
                continue

            omstream = LatentChannel[ClientPrivmsg | str](5)
            osstream = TwitchChannel(socket)
            dbstream = SQLiteChannel(connection)

            transports = [
                Transport(
                    pipe,
                    Channel[IRCv3CommandProtocol](),
                    omstream=omstream,
                    osstream=osstream,
                    dbstream=dbstream,
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
