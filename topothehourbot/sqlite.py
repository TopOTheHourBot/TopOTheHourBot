from __future__ import annotations

__all__ = [
    "PARSE_COLNAMES",
    "PARSE_DECLTYPES",
    "Statement",
    "ColumnDef",
    "ColumnOrdering",
    "Create",
    "Select",
    "Insert",
    "SQLiteConnection",
    "register_adapter",
    "register_converter",
    "connect",
]

import sqlite3
from abc import abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from sqlite3 import PARSE_COLNAMES, PARSE_DECLTYPES
from typing import Literal, Optional, Protocol, final, overload, override

import aiosqlite
from aiosqlite import register_adapter, register_converter
from aiosqlite.context import Result
from aiosqlite.cursor import Cursor

type PathLike = Path | str
type SQLiteObject = str | bytes | int | float | object | None
type Parameters = Sequence[SQLiteObject] | Mapping[str, SQLiteObject]


class Statement(Protocol):

    @abstractmethod
    def __str__(self) -> str:
        """Convert the statement to an executable string"""
        raise NotImplementedError

    @property
    def parameters(self) -> Parameters:
        """The statement parameters

        Set to an empty sequence if the statement has no parameters.
        """
        return ()


@final
@dataclass(slots=True, kw_only=True)
class ColumnDef:

    name: str
    type: str
    not_null: bool = True

    def __str__(self) -> str:
        parts = [self.name]
        parts.append(str(self.type))
        if self.not_null:
            parts.append("NOT NULL")
        return " ".join(parts)


@final
@dataclass(slots=True, kw_only=True)
class ColumnOrdering:

    name: str
    order: Literal["ASC", "DESC"] = "ASC"
    order_nulls: Literal["FIRST", "LAST"] = "FIRST"

    def __str__(self) -> str:
        return f"{self.name} {self.order} NULLS {self.order_nulls}"


@final
@dataclass(init=False, slots=True)
class Create(Statement):

    table: str
    columns: Sequence[ColumnDef | str]
    if_not_exists: bool

    def __init__(self, *, table: str, columns: Sequence[ColumnDef | str], if_not_exists: bool = True) -> None:
        if __debug__:
            if not columns:
                raise ValueError("table must have at least one column")
        self.table = table
        self.columns = columns
        self.if_not_exists = if_not_exists

    @override
    def __str__(self) -> str:
        parts = ["CREATE TABLE"]
        if self.if_not_exists:
            parts.append("IF NOT EXISTS")
        parts.append(self.table)
        parts.append("(")
        columns = tuple(map(str, self.columns))
        i = len(columns) - 1
        for column in map(columns.__getitem__, range(i)):
            parts.append(column)
            parts.append(",")
        parts.append(columns[i])
        parts.append(")")
        return " ".join(parts)


@final
@dataclass(slots=True, kw_only=True)
class Select(Statement):

    table: str
    columns: Sequence[str] = ()
    order_by: Sequence[ColumnOrdering] = ()
    limit: Optional[int] = None
    distinct: bool = False

    @override
    def __str__(self) -> str:
        parts = ["SELECT"]
        if self.distinct:
            parts.append("DISTINCT")

        if (columns := self.columns):
            i = len(columns) - 1
            for column_name in map(columns.__getitem__, range(i)):
                parts.append(column_name)
                parts.append(",")
            parts.append(columns[i])
        else:
            parts.append("*")

        parts.append("FROM")
        parts.append(self.table)

        if (order_by := self.order_by):
            order_by_columns = tuple(map(str, order_by))
            parts.append("ORDER BY")
            i = len(order_by_columns) - 1
            for column_name in map(order_by_columns.__getitem__, range(i)):
                parts.append(column_name)
                parts.append(",")
            parts.append(order_by_columns[i])

        if (limit := self.limit) is not None:
            parts.append("LIMIT")
            parts.append(str(limit))

        return " ".join(parts)


@final
@dataclass(slots=True, kw_only=True)
class Insert(Statement):

    table: str
    row: Mapping[str, SQLiteObject]

    @override
    def __str__(self) -> str:
        parts = ["INSERT INTO", self.table, "("]

        keys = tuple(self.row.keys())

        i = len(keys) - 1
        for key in map(keys.__getitem__, range(i)):
            parts.append(key)
            parts.append(",")
        parts.append(keys[i])
        parts.append(")")

        parts.extend(("VALUES", "("))
        for key in map(keys.__getitem__, range(i)):
            parts.append(":" + key)
            parts.append(",")
        parts.append(":" + keys[i])
        parts.append(")")

        return " ".join(parts)

    @property
    @override
    def parameters(self) -> Mapping[str, SQLiteObject]:
        return self.row


class SQLiteConnection:

    __slots__ = ("_connection")
    _connection: aiosqlite.Connection

    def __init__(self, connection: aiosqlite.Connection) -> None:
        self._connection = connection

    @overload
    def execute(self, statement: str, parameters: Parameters = ()) -> Result[Cursor]: ...
    @overload
    def execute(self, statement: Statement) -> Result[Cursor]: ...

    def execute(self, statement: Statement | str, parameters: Parameters = ()) -> Result[Cursor]:
        """Execute a given statement"""
        if not isinstance(statement, str):
            parameters = statement.parameters
        statement = str(statement)
        return self._connection.execute(statement, parameters)

    def select(
        self,
        table: str,
        *,
        columns: Sequence[str],
        order_by: Sequence[ColumnOrdering] = (),
        limit: Optional[int] = None,
        distinct: bool = False,
    ) -> Result[Cursor]:
        return self.execute(
            Select(
                table=table,
                columns=columns,
                order_by=order_by,
                limit=limit,
                distinct=distinct,
            ),
        )

    async def create(
        self,
        table: str,
        *,
        columns: Sequence[ColumnDef | str],
        if_not_exists: bool = True,
    ) -> None:
        await self.execute(
            Create(
                table=table,
                columns=columns,
                if_not_exists=if_not_exists,
            ),
        )

    async def insert(self, table: str, *, row: Mapping[str, SQLiteObject]) -> None:
        await self.execute(
            Insert(
                table=table,
                row=row,
            ),
        )

    async def commit(self) -> None:
        """Commit the current transaction"""
        await self._connection.commit()

    async def close(self) -> None:
        """Complete the currently-enqueued queries and close the connection"""
        await self._connection.close()


async def connect(
    path: PathLike,
    *,
    connection_factory: type[sqlite3.Connection] = sqlite3.Connection,
    chunk_size: int = 64,
    timeout: float = 5,
    detect_types: int = 0,
    isolation_level: Optional[str] = "DEFERRED",
    check_same_thread: bool = True,
    cached_statements: int = 128,
    uri: bool = False,
    autocommit: bool = False,
) -> SQLiteConnection:
    connection = await aiosqlite.connect(
        path,
        factory=connection_factory,
        iter_chunk_size=chunk_size,
        timeout=timeout,
        detect_types=detect_types,
        isolation_level=isolation_level,
        check_same_thread=check_same_thread,
        cached_statements=cached_statements,
        uri=uri,
        autocommit=autocommit,
    )
    return SQLiteConnection(connection)
