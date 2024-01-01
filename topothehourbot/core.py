from __future__ import annotations

__all__ = [
    "TopOTheHourBotConfiguration",
    "TopOTheHourBot",
]

from dataclasses import dataclass
from typing import override

from websockets import WebSocketClientProtocol

from .system import Client
from .utilities import Configuration


@dataclass(slots=True, kw_only=True)
class TopOTheHourBotConfiguration(Configuration):
    """Configurable attributes for ``TopOTheHourBot``"""

    name: str = "topothehourbot"


class TopOTheHourBot(Client):
    """TopOTheHourBot's client"""

    __slots__ = ("config")
    config: TopOTheHourBotConfiguration

    def __init__(
        self,
        connection: WebSocketClientProtocol,
        *,
        config: TopOTheHourBotConfiguration = TopOTheHourBotConfiguration(),
    ) -> None:
        super().__init__(connection)
        self.config = config

    @property
    @override
    def name(self) -> str:
        return self.config.name
