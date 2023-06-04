from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from typing import Any, TypeVar

from websockets import client
from websockets.exceptions import ConnectionClosed
from websockets.typing import Data

from .reader import Reader
from .streams import IOStream, UnboundedIOStream
from .task_manager import TaskManager
from .writer import Writer

__all__ = ["connect"]

ReadingT = TypeVar("ReadingT")
WritingT = TypeVar("WritingT")


async def connect(
    uri: str,
    writer: Writer[WritingT],
    readers: Sequence[Reader[ReadingT, WritingT]],
    *,
    parser: Callable[[Data], ReadingT] = lambda data: data,
    **kwargs: Any,
) -> None:
    tasks = TaskManager()
    writer_stream  = IOStream[WritingT](capacity=1)
    reader_streams = [
        UnboundedIOStream[ReadingT]()
        for _ in range(len(readers))
    ]
    async for socket in client.connect(uri, **kwargs):
        try:
            tasks.create_task(writer(writer_stream, socket))
            for reader, reader_stream in zip(
                readers,
                reader_streams,
            ):
                tasks.create_task(reader(reader_stream, writer_stream))
            async for data in socket:
                result = parser(data)
                for reader_stream in reader_streams:
                    reader_stream.put(result)
        except ConnectionClosed as exc:
            logging.exception(exc)
            await tasks.cancel()
            continue
