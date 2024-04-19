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
class SupportsOnWebSocketData(Protocol):
    def on_websocket_data(self, websocket: WebSocket, data: Data, /) -> CallbackReturn: ...

type SupportsWebSocketCallback = (
    SupportsOnWebSocketConnect
    | SupportsOnWebSocketDisconnect
    | SupportsOnWebSocketData
)


class WebSocketApp:

    __slots__ = ("connect_signal", "disconnect_signal", "data_signal")
    connect_signal: Signal[[WebSocket]]
    disconnect_signal: Signal[[WebSocket]]
    data_signal: Signal[[WebSocket, Data]]

    def __init__(self) -> None:
        self.connect_signal = Signal()
        self.disconnect_signal = Signal()
        self.data_signal = Signal()

    def add_callbacks(self, suite: SupportsWebSocketCallback) -> Self:
        if isinstance(suite, SupportsOnWebSocketConnect):
            self.connect_signal.add_callback(suite.on_websocket_connect)
        if isinstance(suite, SupportsOnWebSocketDisconnect):
            self.disconnect_signal.add_callback(suite.on_websocket_disconnect)
        if isinstance(suite, SupportsOnWebSocketData):
            self.data_signal.add_callback(suite.on_websocket_data)
        return self

    def remove_callbacks(self, suite: SupportsWebSocketCallback) -> Self:
        if isinstance(suite, SupportsOnWebSocketConnect):
            self.connect_signal.remove_callback(suite.on_websocket_connect)
        if isinstance(suite, SupportsOnWebSocketDisconnect):
            self.disconnect_signal.remove_callback(suite.on_websocket_disconnect)
        if isinstance(suite, SupportsOnWebSocketData):
            self.data_signal.remove_callback(suite.on_websocket_data)
        return self

    async def run(self, uri: str) -> None:
        async for protocol in websockets.connect(uri):
            try:
                websocket = WebSocket(protocol, self)
                waiter = self.connect_signal.maybe_run(websocket)
                if waiter:
                    await waiter
                async for data in protocol:
                    websocket = WebSocket(protocol, self)
                    self.data_signal.run(websocket, data)
            except ConnectionClosedError:
                continue
            else:
                close_code = protocol.close_code
                if close_code == 1000:
                    websocket = WebSocket(protocol, self)
                    waiter = self.disconnect_signal.maybe_run(websocket)
                    if waiter:
                        await waiter
                    return
                if close_code == 1001:
                    continue
                raise RuntimeError(f"Unrecognized non-error close code, {close_code}")


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

    async def send(self, data: Data | Iterable[Data] | AsyncIterable[Data]) -> None:
        await self._protocol.send(data)

    async def close(self, code: int = 1000, reason: str = "") -> None:
        await self._protocol.close(code, reason)
