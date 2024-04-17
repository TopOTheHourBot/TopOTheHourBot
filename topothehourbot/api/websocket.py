from __future__ import annotations

__all__ = ["WebSocketApp", "WebSocket"]

from collections.abc import AsyncIterable, Iterable
from typing import Protocol, Self, runtime_checkable

import websockets
from websockets import ConnectionClosed, Data, WebSocketClientProtocol
from websockets.frames import CloseCode

from .utilities import Signal


@runtime_checkable
class SupportsOnWebSocketConnect(Protocol):
    async def on_websocket_connect(self, websocket: WebSocket, /) -> object: ...

@runtime_checkable
class SupportsOnWebSocketDisconnect(Protocol):
    async def on_websocket_disconnect(self, websocket: WebSocket, /) -> object: ...

@runtime_checkable
class SupportsOnWebSocketText(Protocol):
    async def on_websocket_text(self, websocket: WebSocket, text: str, /) -> object: ...

@runtime_checkable
class SupportsOnWebSocketBinary(Protocol):
    async def on_websocket_binary(self, websocket: WebSocket, binary: bytes, /) -> object: ...

type SupportsWebSocketCallback = (
    SupportsOnWebSocketConnect
    | SupportsOnWebSocketDisconnect
    | SupportsOnWebSocketText
    | SupportsOnWebSocketBinary
)


class WebSocketApp:

    __slots__ = ("connect_signal", "disconnect_signal", "text_signal", "binary_signal")
    connect_signal: Signal[[WebSocket], object]
    disconnect_signal: Signal[[WebSocket], object]
    text_signal: Signal[[WebSocket, str], object]
    binary_signal: Signal[[WebSocket, bytes], object]

    def __init__(self) -> None:
        self.connect_signal = Signal()
        self.disconnect_signal = Signal()
        self.text_signal = Signal()
        self.binary_signal = Signal()

    def add_callbacks(self, suite: SupportsWebSocketCallback) -> Self:
        if isinstance(suite, SupportsOnWebSocketConnect):
            self.connect_signal.add_callback(suite.on_websocket_connect)
        if isinstance(suite, SupportsOnWebSocketDisconnect):
            self.disconnect_signal.add_callback(suite.on_websocket_disconnect)
        if isinstance(suite, SupportsOnWebSocketText):
            self.text_signal.add_callback(suite.on_websocket_text)
        if isinstance(suite, SupportsOnWebSocketBinary):
            self.binary_signal.add_callback(suite.on_websocket_binary)
        return self

    def remove_callbacks(self, suite: SupportsWebSocketCallback) -> Self:
        if isinstance(suite, SupportsOnWebSocketConnect):
            self.connect_signal.remove_callback(suite.on_websocket_connect)
        if isinstance(suite, SupportsOnWebSocketDisconnect):
            self.disconnect_signal.remove_callback(suite.on_websocket_disconnect)
        if isinstance(suite, SupportsOnWebSocketText):
            self.text_signal.remove_callback(suite.on_websocket_text)
        if isinstance(suite, SupportsOnWebSocketBinary):
            self.binary_signal.remove_callback(suite.on_websocket_binary)
        return self

    async def run(self, uri: str) -> None:
        async for protocol in websockets.connect(uri):
            try:
                waiter = self.connect_signal.maybe_run(WebSocket(protocol, self))
                if waiter:
                    await waiter
                async for data in protocol:
                    websocket = WebSocket(protocol, self)
                    if isinstance(data, bytes):
                        self.binary_signal.maybe_run(websocket, data)
                    else:
                        self.text_signal.maybe_run(websocket, data)
            except ConnectionClosed:
                waiter = self.disconnect_signal.maybe_run(WebSocket(protocol, self))
                if waiter:
                    await waiter


class WebSocket:

    __slots__ = ("_protocol", "app")
    _protocol: WebSocketClientProtocol
    app: WebSocketApp

    def __init__(self, protocol: WebSocketClientProtocol, app: WebSocketApp) -> None:
        self._protocol = protocol
        self.app = app

    @property
    def latency(self) -> float:
        return self._protocol.latency * 1000

    @property
    def open(self) -> bool:
        return self._protocol.open

    @property
    def closed(self) -> bool:
        return self._protocol.closed

    @property
    def close_code(self) -> int | None:
        return self._protocol.close_code

    @property
    def close_reason(self) -> str | None:
        return self._protocol.close_reason

    async def send(
        self,
        data: Data | Iterable[Data] | AsyncIterable[Data],
    ) -> None:
        await self._protocol.send(data)

    async def close(
        self,
        code: int = CloseCode.NORMAL_CLOSURE,
        reason: str = "",
    ) -> None:
        await self._protocol.close(code, reason)
