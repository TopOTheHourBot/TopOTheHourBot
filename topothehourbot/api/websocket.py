from __future__ import annotations

__all__ = ["WebSocketApp", "WebSocket"]

from collections.abc import AsyncIterable, Iterable
from typing import Protocol, Self, runtime_checkable

import websockets
from websockets import ConnectionClosedError, Data, WebSocketClientProtocol

from .utilities import CallbackReturn, Signal


@runtime_checkable
class SupportsOnWebSocketConnect(Protocol):
    def on_websocket_connect(self, websocket: WebSocket, /) -> CallbackReturn: ...

@runtime_checkable
class SupportsOnWebSocketDisconnect(Protocol):
    def on_websocket_disconnect(self, websocket: WebSocket, /) -> CallbackReturn: ...

@runtime_checkable
class SupportsOnWebSocketText(Protocol):
    def on_websocket_text(self, websocket: WebSocket, text: str, /) -> CallbackReturn: ...

@runtime_checkable
class SupportsOnWebSocketBinary(Protocol):
    def on_websocket_binary(self, websocket: WebSocket, binary: bytes, /) -> CallbackReturn: ...

type SupportsWebSocketCallback = (
    SupportsOnWebSocketConnect
    | SupportsOnWebSocketDisconnect
    | SupportsOnWebSocketText
    | SupportsOnWebSocketBinary
)


class WebSocketApp:

    __slots__ = ("connect_signal", "disconnect_signal", "text_signal", "binary_signal")
    connect_signal: Signal[[WebSocket]]
    disconnect_signal: Signal[[WebSocket]]
    text_signal: Signal[[WebSocket, str]]
    binary_signal: Signal[[WebSocket, bytes]]

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
                # Normal closures (codes 1000 and 1001) exit
                # `protocol.__aiter__()` gracefully. We use code 1000 for
                # closure requests in WebSocket, and so we must do a raw
                # `break` here.
                async for data in protocol:
                    websocket = WebSocket(protocol, self)
                    if isinstance(data, bytes):
                        self.binary_signal.maybe_run(websocket, data)
                    else:
                        self.text_signal.maybe_run(websocket, data)
                break
            except ConnectionClosedError:
                continue


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

    async def close(self) -> None:
        await self._protocol.close()
