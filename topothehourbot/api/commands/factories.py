from __future__ import annotations

__all__ = ["handle", "room"]


def handle(argument: str, /) -> str:
    """Return ``argument`` formatted as a Twitch handle"""
    return "@" + argument.lstrip("@")


def room(argument: str, /) -> str:
    """Return ``argument`` formatted as a Twitch room"""
    return "#" + argument.lstrip("#")
