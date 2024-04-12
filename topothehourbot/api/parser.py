from __future__ import annotations

__all__ = ["ServerCommandParser"]

from collections.abc import Iterator
from typing import Final, Self

from ircv3 import Command, ServerCommandProtocol
from ircv3.common import Ping, Welcome
from ircv3.twitch import RoomState, ServerJoin, ServerMessage, ServerPart


class ServerCommandParser(Iterator[ServerCommandProtocol]):

    TYPE_MAP = {
        "PRIVMSG": ServerMessage,
        "ROOMSTATE": RoomState,
        "PING": Ping,
        "JOIN": ServerJoin,
        "PART": ServerPart,
        "001": Welcome,
    }

    UNRECOGNIZED: Final[object] = object()
    EXHAUSTED: Final[object] = object()

    __slots__ = ("_data", "_head")
    _data: str
    _head: int

    def __init__(self, data: str) -> None:
        self._data = data
        self._head = 0

    def __iter__(self) -> Self:
        return self

    def __next__(self) -> ServerCommandProtocol:
        while (result := self._move_head()) is not self.EXHAUSTED:
            if result is self.UNRECOGNIZED:
                continue
            assert isinstance(result, ServerCommandProtocol)
            return result
        raise StopIteration

    def _move_head(self) -> object:
        head = self._head
        if head == -1:
            return self.EXHAUSTED
        data = self._data
        next = data.find("\r\n", head)
        if next == -1:
            self._head = next
            return self.EXHAUSTED
        self._head = next + 2  # Size of "\r\n"
        command = Command.from_string(data[head:next])
        type = self.TYPE_MAP.get(command.name)
        if type is None:
            return self.UNRECOGNIZED
        return type.cast(command)
