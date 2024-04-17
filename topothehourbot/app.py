from . import hasanabi
from .api.client import ClientApp

app = (
    ClientApp(
        oauth_token="...",
        name="topothehourbot",
    )
    .add_callbacks(hasanabi.commands)
    .add_callbacks(hasanabi.common)
    .add_callbacks(hasanabi.ratings)
)
