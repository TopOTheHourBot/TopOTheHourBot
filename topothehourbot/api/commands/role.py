from __future__ import annotations

__all__ = ["Role"]

from enum import Enum
from typing import Self

from ircv3.dialects.twitch import ExternalClient


class Role(Enum):

    NONE = 0
    SUBSCRIBER = 1
    VIP = 2
    MODERATOR = 3
    BROADCASTER = 4

    @classmethod
    def from_client(cls, client: ExternalClient) -> Self:
        if client.broadcaster:
            value = 4
        elif client.moderator:
            value = 3
        elif client.vip:
            value = 2
        elif client.subscriber:
            value = 1
        else:
            value = 0
        return cls(value)
