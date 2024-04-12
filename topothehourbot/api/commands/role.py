from __future__ import annotations

__all__ = ["Role"]

from enum import Enum
from typing import Self

from ircv3.twitch import ExternalClient


class Role(Enum):
    """An enum whose members represent the five roles of a channeled Twitch
    user

    Each member is assigned a number respective to their level of "channel
    privilege". From lowest to highest, there is: ``NONE``, ``SUBSCRIBER``,
    ``VIP``, ``MODERATOR``, and ``BROADCASTER``.

    This ordering of roles allows for easy categorization of levels above and
    below a certain privilege, as is often required for command interfaces. Use
    the comparison operators to make assessments, e.g.,
    ``Role.MODERATOR >= Role.SUBSCRIBER`` (evaluates true, since moderators
    have greater privileges than a subscriber).
    """

    NONE = 0
    """User has no role respective to the channel"""
    SUBSCRIBER = 1
    """User is a subscriber to the channel"""
    VIP = 2
    """User is a VIP of the channel"""
    MODERATOR = 3
    """User is a moderator of the channel"""
    BROADCASTER = 4
    """User is the broadcaster of the channel"""

    def __eq__(self, other: object) -> bool:
        if self is other:
            return True
        if isinstance(other, Role):
            return self.value == other.value
        return NotImplemented

    def __gt__(self, other: object) -> bool:
        if isinstance(other, Role):
            return self.value > other.value
        return NotImplemented

    def __ge__(self, other: object) -> bool:
        if isinstance(other, Role):
            return self.value >= other.value
        return NotImplemented

    def __lt__(self, other: object) -> bool:
        if isinstance(other, Role):
            return self.value < other.value
        return NotImplemented

    def __le__(self, other: object) -> bool:
        if isinstance(other, Role):
            return self.value <= other.value
        return NotImplemented

    @classmethod
    def from_client(cls, client: ExternalClient) -> Self:
        """Return the highest ``Role`` assignable to the given client"""
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
