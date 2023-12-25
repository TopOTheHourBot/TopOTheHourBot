from __future__ import annotations

__all__ = ["ClientExtension"]

from collections.abc import Coroutine
from contextlib import AbstractContextManager
from typing import Any, Optional

from channels import Channel, Diverter
from ircv3.dialects.twitch import (ServerPrivateMessage,
                                   SupportsClientProperties)
from websockets import ConnectionClosed

from .client import Client


class ClientExtension[DistributeT](SupportsClientProperties):
    """A wrapper type around an ``Client`` instance with an independent
    diverter, allowing objects of any type to be distributed

    Note that this class does not have a distributor by default. How and when
    distribution occurs is left up to the sub-class implementor.

    This class contains no abstracts.
    """

    __slots__ = ("_client", "_diverter")
    _client: Client
    _diverter: Diverter[DistributeT]

    def __init__(self, client: Client) -> None:
        self._client = client
        self._diverter = Diverter()

    @property
    def name(self) -> str:
        """The client's source IRC name"""
        return self._client.name

    @property
    def latency(self) -> float:
        """The connection latency in milliseconds

        Updated with each ping sent by the underlying connection. Set to ``0``
        before the first ping.
        """
        return self._client.latency

    def join(self, *rooms: str) -> Coroutine[Any, Any, Optional[ConnectionClosed]]:
        """Send a JOIN command to the IRC server"""
        return self._client.join(*rooms)

    def part(self, *rooms: str) -> Coroutine[Any, Any, Optional[ConnectionClosed]]:
        """Send a PART command to the IRC server"""
        return self._client.part(*rooms)

    def message(
        self,
        comment: str,
        target: ServerPrivateMessage | str,
        *,
        important: bool = False,
    ) -> Coroutine[Any, Any, Optional[ConnectionClosed]]:
        """Send a PRIVMSG command to the IRC server

        Composes a ``ClientPrivateMessage`` in reply to ``target`` if a
        ``ServerPrivateMessage``, or to the room named by ``target`` if a
        ``str``.

        PRIVMSGs have a global 1.5-second cooldown. ``important`` can be set to
        true to wait for the cooldown, or false to prevent waiting when a
        dispatch occurs during a cooldown period.
        """
        return self._client.message(comment, target, important=important)

    def close(self) -> Coroutine[Any, Any, None]:
        """Close the connection to the IRC server"""
        return self._client.close()

    def until_closure(self) -> Coroutine[Any, Any, None]:
        """Wait until the IRC connection has been closed"""
        return self._client.until_closure()

    def attachment(
        self,
        channel: Optional[Channel[DistributeT]] = None,
    ) -> AbstractContextManager[Channel[DistributeT]]:
        """Return a context manager that safely attaches and detaches
        ``channel``

        Default-constructs a ``Channel`` instance if ``channel`` is ``None``.
        """
        return self._diverter.attachment(channel)
