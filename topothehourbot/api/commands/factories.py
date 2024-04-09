from __future__ import annotations

__all__ = ["handle"]


def handle(argument: str, /) -> str:
    """Return ``argument`` formatted as a Twitch handle"""
    return "@" + argument.lstrip("@")
