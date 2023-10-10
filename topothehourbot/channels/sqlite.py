from __future__ import annotations

__all__ = ["SQLiteChannel"]

from collections.abc import Mapping, Sequence
from typing import Any, Coroutine, override

from aiosqlite import Connection, Cursor
from aiosqlite.context import Result
from channels import SupportsSend


class SQLiteChannel(SupportsSend[str]):

    __slots__ = ("_connection")
    _connection: Connection

    def __init__(self, connection: Connection, /) -> None:
        self._connection = connection

    @override
    def send(self, expr: str, params: Sequence[object] | Mapping[str, object] = ()) -> Result[Cursor]:
        return self._connection.execute(expr, params)

    def commit(self) -> Coroutine[Any, Any, None]:
        return self._connection.commit()
