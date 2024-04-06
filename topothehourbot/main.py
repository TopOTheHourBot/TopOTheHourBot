from __future__ import annotations

__all__ = ["app"]

from .api.client import Client

app = (
    Client(
        oauth_token="...",
        name="topothehourbot",
    )
)
