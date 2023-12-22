from __future__ import annotations

__all__ = ["IRCv3ServerCommandParser"]

from collections.abc import Iterator
from typing import Final, Self

from ircv3 import IRCv3Command, IRCv3ServerCommandProtocol, Ping
from ircv3.dialects.twitch import (RoomState, ServerJoin, ServerPart,
                                   ServerPrivateMessage)


class IRCv3ServerCommandParser(Iterator[IRCv3ServerCommandProtocol]):

    NIL: Final[object] = object()
    END: Final[object] = object()

    __slots__ = ("_data", "_head")
    _data: str
    _head: int

    def __init__(self, data: str, *, head: int = 0) -> None:
        self._data = data
        self._head = head

    def __iter__(self) -> Self:
        return self

    def __next__(self) -> IRCv3ServerCommandProtocol:
        while (result := self.move_head()) is not self.END:
            if result is self.NIL:
                continue
            assert isinstance(result, IRCv3ServerCommandProtocol)
            return result
        raise StopIteration

    def move_head(self) -> object:
        head = self._head
        if head == -1:
            return self.END
        data = self._data
        next = data.find("\r\n", head)
        if next == -1:
            self._head = next
            return self.END
        command = IRCv3Command.from_string(data[head:next])
        name = command.name
        self._head = next + 2
        if name == "PRIVMSG":
            return ServerPrivateMessage.cast(command)
        elif name == "ROOMSTATE":
            return RoomState.cast(command)
        elif name == "PING":
            return Ping.cast(command)
        elif name == "JOIN":
            return ServerJoin.cast(command)
        elif name == "PART":
            return ServerPart.cast(command)
        return self.NIL
