from __future__ import annotations

__all__ = ["ServerCommandParser"]

from collections.abc import Iterator
from typing import Final, Literal, Self

from ircv3 import Command, Ping, ServerCommandProtocol
from ircv3.dialects.twitch import (RoomState, ServerJoin, ServerPart,
                                   ServerPrivateMessage)


class ServerCommandParser(Iterator[ServerCommandProtocol]):

    CRLF: Final[Literal["\r\n"]] = "\r\n"

    UNRECOGNIZED: Final[object] = object()
    EXHAUSTED: Final[object] = object()

    __slots__ = ("_data", "_head")
    _data: str
    _head: int

    def __init__(self, data: str, *, head: int = 0) -> None:
        self._data = data
        self._head = head

    def __iter__(self) -> Self:
        return self

    def __next__(self) -> ServerCommandProtocol:
        while (result := self.move_head()) is not self.EXHAUSTED:
            if result is self.UNRECOGNIZED:
                continue
            assert isinstance(result, ServerCommandProtocol)
            return result
        raise StopIteration

    def move_head(self) -> object:
        head = self._head
        if head == -1:
            return self.EXHAUSTED
        data = self._data
        next = data.find(self.CRLF, head)
        if next == -1:
            self._head = next
            return self.EXHAUSTED
        command = Command.from_string(data[head:next])
        name = command.name
        self._head = next + len(self.CRLF)
        if name == "PRIVMSG":
            return ServerPrivateMessage.cast(command)
        if name == "ROOMSTATE":
            return RoomState.cast(command)
        if name == "PING":
            return Ping.cast(command)
        if name == "JOIN":
            return ServerJoin.cast(command)
        if name == "PART":
            return ServerPart.cast(command)
        return self.UNRECOGNIZED
