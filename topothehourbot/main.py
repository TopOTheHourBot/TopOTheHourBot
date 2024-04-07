from __future__ import annotations

__all__ = ["topothehourbot"]

from . import hasanabi
from .api.client import Client

topothehourbot = (
    Client(
        oauth_token="...",
        name="topothehourbot",
    )
    .add_callbacks(hasanabi.channel)
)
