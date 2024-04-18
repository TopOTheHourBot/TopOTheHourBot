from __future__ import annotations

__all__ = ["handle_factory", "room_factory"]

# TODO: Might be better to validate these with regex


def handle_factory(argument: str, /) -> str:
    """Return ``argument`` formatted as a Twitch handle"""
    return "@" + argument.lstrip("@")


def room_factory(argument: str, /) -> str:
    """Return ``argument`` formatted as a Twitch room"""
    return "#" + argument.lstrip("#")
