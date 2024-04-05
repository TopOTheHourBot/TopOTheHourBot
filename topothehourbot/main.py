from __future__ import annotations

__all__ = ["app"]

from . import hasanabi
from .api.app import ClientApp

app = (
    ClientApp(
        oauth_token="...",
        name="topothehourbot",
    )
    .load(hasanabi.app)
)
