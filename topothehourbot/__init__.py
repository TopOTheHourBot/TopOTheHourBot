from __future__ import annotations

__all__ = ["client"]

from . import hasanabi
from .api.client import Client

client = (
    Client(
        oauth_token="...",
        name="topothehourbot",
    )
    .add_callbacks(hasanabi.channel)
)
